"""The only module that talks to LLMs (AGENTS.md, architecture rules).

Chooses provider/model from config/models.yaml, builds the chat model with LangChain's
``init_chat_model`` and records every call as a RunRecord in runs/*.jsonl.
"""

from pathlib import Path
from typing import Any, Literal, cast, get_args

import yaml
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, ConfigDict, Field, ValidationError

Provider = Literal["bedrock", "gemini", "groq"]

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODELS_PATH = REPO_ROOT / "config" / "models.yaml"

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
