"""The only module that talks to LLMs (AGENTS.md, architecture rules).

Chooses provider/model from config/models.yaml, builds the chat model with LangChain's
``init_chat_model`` and records every call as a RunRecord in runs/*.jsonl.
"""

import hashlib
import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast, get_args

import yaml
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from mia.schemas import RunRecord

Provider = Literal["bedrock", "gemini", "groq"]

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODELS_PATH = REPO_ROOT / "config" / "models.yaml"
DEFAULT_RUNS_DIR = REPO_ROOT / "runs"
NO_EXPERIMENT = "adhoc"  # file name part when experiment is None

# Our provider names (RunRecord.provider) -> LangChain's model_provider names.
LANGCHAIN_PROVIDERS: dict[Provider, str] = {
    "bedrock": "bedrock_converse",
    "gemini": "google_genai",
    "groq": "groq",
}


class ModelConfigError(Exception):
    """config/models.yaml is invalid or a model reference can't be resolved."""


class ModelSpec(BaseModel):
    """One catalog entry: which model to call and how much it costs."""

    model_config = ConfigDict(extra="forbid")

    ref: str  # "provider:model_id", e.g. "gemini:gemini-2.5-flash"
    provider: Provider
    model: str  # model id at the provider
    usd_per_mtok_input: float = Field(ge=0)
    usd_per_mtok_output: float = Field(ge=0)
    free_tier: bool = False  # True: free usage; price is the published paid rate (reference)


class ModelsConfig(BaseModel):
    default: str
    models: dict[str, ModelSpec]


def _split_ref(ref: str, where: str) -> tuple[Provider, str]:
    """Split "provider:model_id" on the first colon (Bedrock ids also contain colons)."""
    provider, sep, model = ref.partition(":")
    if not sep or not provider or not model:
        raise ModelConfigError(f"{where}: {ref!r} is not in the 'provider:model' format")
    if provider not in get_args(Provider):
        raise ModelConfigError(
            f"{where}: unknown provider {provider!r} in {ref!r} "
            f"(expected one of {', '.join(get_args(Provider))})"
        )
    return cast(Provider, provider), model


def _describe(exc: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}" for err in exc.errors()
    )


def _parse_model(ref: Any, fields: Any, path: Path) -> ModelSpec:
    where = f"{path}: models.{ref}"
    if not isinstance(fields, dict):
        raise ModelConfigError(f"{where}: entry must be a mapping of fields")
    for field in ("ref", "provider", "model"):
        if field in fields:
            raise ModelConfigError(
                f"{where}.{field}: derived from the catalog key; omit this field"
            )
    provider, model = _split_ref(str(ref), str(path))
    try:
        return ModelSpec(ref=str(ref), provider=provider, model=model, **fields)
    except ValidationError as exc:
        raise ModelConfigError(f"{where}: {_describe(exc)}") from exc


def load_models_config(path: Path = DEFAULT_MODELS_PATH) -> ModelsConfig:
    """Read and validate the model catalog."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ModelConfigError(f"{path}: cannot read models config ({exc})") from exc

    if not isinstance(raw, dict) or not isinstance(raw.get("models"), dict):
        raise ModelConfigError(f"{path}: 'models' must map 'provider:model' to its fields")

    models = {str(ref): _parse_model(ref, fields, path) for ref, fields in raw["models"].items()}
    default = raw.get("default")
    if not isinstance(default, str):
        raise ModelConfigError(f"{path}: default must be a 'provider:model' string")
    if default not in models:
        raise ModelConfigError(f"{path}: default {default!r} is not one of the models")
    return ModelsConfig(default=default, models=models)


def resolve_model(ref: str | None, config: ModelsConfig) -> ModelSpec:
    """Find a model by "provider:model_id"; None means the config default."""
    ref = config.default if ref is None else ref
    _split_ref(ref, "model reference")
    if ref not in config.models:
        raise ModelConfigError(f"model {ref!r} is not in the models config (no price to record)")
    return config.models[ref]


def build_chat_model(spec: ModelSpec, params: dict[str, Any]) -> BaseChatModel:
    """The single place that instantiates a provider model."""
    return init_chat_model(spec.model, model_provider=LANGCHAIN_PROVIDERS[spec.provider], **params)


def estimate_cost(spec: ModelSpec, input_tokens: int, output_tokens: int) -> float:
    cost = (
        input_tokens * spec.usd_per_mtok_input + output_tokens * spec.usd_per_mtok_output
    ) / 1_000_000
    return round(cost, 8)


def hash_input(system: str, user: str) -> str:
    """SHA-256 of the exact messages sent; same messages -> same hash (cache, consistency)."""
    canonical = json.dumps({"system": system, "user": user}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def append_run_record(record: RunRecord, runs_dir: Path = DEFAULT_RUNS_DIR) -> Path:
    """Append one JSON line to runs/<UTC date>_<experiment>.jsonl and return the file path."""
    runs_dir.mkdir(parents=True, exist_ok=True)
    name = f"{record.created_at.date().isoformat()}_{record.experiment or NO_EXPERIMENT}.jsonl"
    path = runs_dir / name
    with path.open("a", encoding="utf-8") as file:
        file.write(record.model_dump_json() + "\n")
    return path


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def invoke(
    *,
    prompt_name: str,
    prompt_version: int,
    system: str,
    user: str,
    input: dict[str, Any],
    model: str | None = None,
    params: dict[str, Any] | None = None,
    experiment: str | None = None,
    session_id: str | None = None,
    config: ModelsConfig | None = None,
    runs_dir: Path = DEFAULT_RUNS_DIR,
    chat_model: BaseChatModel | None = None,
) -> str:
    """Call the model with already-rendered messages, record a RunRecord, return the text.

    ``input`` holds the (already masked) variables, saved as-is in the record.
    ``chat_model`` lets tests inject a fake model; by default it is built from the config.
    """
    spec = resolve_model(model, config or load_models_config())
    params = dict(params or {})
    llm = chat_model or build_chat_model(spec, params)

    record = {
        "run_id": uuid.uuid4().hex,
        "experiment": experiment,
        "session_id": session_id,
        "prompt_name": prompt_name,
        "prompt_version": prompt_version,
        "provider": spec.provider,
        "model": spec.model,
        "params": params,
        "input_hash": hash_input(system, user),
        "input": input,
        "output_parsed": None,  # structured output arrives in task 1.5
        "json_valid_first_try": None,
        "repaired": None,
        "created_at": datetime.now(UTC),
    }

    started = time.perf_counter()
    try:
        response = llm.invoke([SystemMessage(system), HumanMessage(user)])
    except Exception as exc:
        failed = RunRecord(
            **record,
            output_raw="",
            input_tokens=0,
            output_tokens=0,
            latency_ms=_elapsed_ms(started),
            cost_usd=0.0,
            error=f"{type(exc).__name__}: {exc}",
        )
        append_run_record(failed, runs_dir)
        raise

    latency_ms = _elapsed_ms(started)
    usage = response.usage_metadata or {}
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    append_run_record(
        RunRecord(
            **record,
            output_raw=response.text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost_usd=estimate_cost(spec, input_tokens, output_tokens),
            error=None,
        ),
        runs_dir,
    )
    return response.text
