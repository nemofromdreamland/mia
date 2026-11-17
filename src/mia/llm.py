"""The only module that talks to LLMs (AGENTS.md, architecture rules).

Chooses provider/model from config/models.yaml, builds the chat model with LangChain's
``init_chat_model`` and records every call as a RunRecord in runs/*.jsonl.
"""

import hashlib
import json
import os
import re
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol, cast, get_args
from urllib.parse import quote, quote_plus

import yaml
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables.retry import ExponentialJitterParams
from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationError

from mia.schemas import RunRecord, VoiceConfig

Provider = Literal["bedrock", "gemini", "groq"]
RecordObserver = Callable[[RunRecord, Path], None]

CREDENTIAL_ENV_NAMES = (
    "GOOGLE_API_KEY",
    "GEMINI_API_KEY",
    "GROQ_API_KEY",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "AWS_BEARER_TOKEN_BEDROCK",
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODELS_PATH = REPO_ROOT / "config" / "models.yaml"
DEFAULT_RUNS_DIR = REPO_ROOT / "runs"
# In the AgentCore container runs/ is ephemeral: with this flag each record also goes to
# stdout (CloudWatch) and scripts/pull_runs.py brings it back into runs/ (spec 4.7b).
RUNS_STDOUT_ENV = "MIA_RUNS_STDOUT"
RUN_RECORD_MARKER = "MIA_RUN_RECORD "
NO_EXPERIMENT = "adhoc"  # file name part when experiment is None

# Wait between retries: exponential backoff from 1 s up to 20 s, plus random jitter
# (covers Groq free-tier 429s). Tests replace it with zeros so they never sleep.
RETRY_WAIT: ExponentialJitterParams = {"initial": 1.0, "max": 20.0}

# Our provider names (RunRecord.provider) -> LangChain's model_provider names.
LANGCHAIN_PROVIDERS: dict[Provider, str] = {
    "bedrock": "bedrock_converse",
    "gemini": "google_genai",
    "groq": "groq",
}


class GuardrailBlocked(Exception):
    """A Bedrock Guardrail intervened (prompt attack, denied topic or PII block)."""


# Tags of the prompts that wrap text coming from outside (candidate, CV, job, transcript).
EXTERNAL_TAGS = ("resposta", "cv", "vaga", "transcricao")
_EXTERNAL_BLOCK = re.compile(
    rf"(<(?P<tag>{'|'.join(EXTERNAL_TAGS)})>)(.*?)(</(?P=tag)>)", re.DOTALL
)
GUARDRAIL_INTERVENED = "guardrail_intervened"


class LLMInvalidOutputError(Exception):
    """Model output failed the schema even after one repair attempt."""


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
    max_retries: StrictInt = Field(default=2, ge=0)  # extra attempts after the first call
    request_timeout_seconds: float = Field(default=60.0, gt=0)


class ModelsConfig(BaseModel):
    default: str
    models: dict[str, ModelSpec]
    prompt_models: dict[str, str] = Field(default_factory=dict)  # prompt name -> model ref


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


def _parse_prompt_models(raw: Any, models: dict[str, ModelSpec], path: Path) -> dict[str, str]:
    """Optional 'prompt_models:' section: prompt name -> catalog ref (per-prompt override)."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ModelConfigError(f"{path}: prompt_models must map a prompt name to a model")
    for name, ref in raw.items():
        if not isinstance(ref, str) or ref not in models:
            raise ModelConfigError(
                f"{path}: prompt_models.{name}: {ref!r} is not one of the models in the catalog"
            )
    return {str(name): ref for name, ref in raw.items()}


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
    prompt_models = _parse_prompt_models(raw.get("prompt_models"), models, path)
    return ModelsConfig(default=default, models=models, prompt_models=prompt_models)


def resolve_model(ref: str | None, config: ModelsConfig) -> ModelSpec:
    """Find a model by "provider:model_id"; None means the config default."""
    ref = config.default if ref is None else ref
    _split_ref(ref, "model reference")
    if ref not in config.models:
        raise ModelConfigError(f"model {ref!r} is not in the models config (no price to record)")
    return config.models[ref]


def build_chat_model(spec: ModelSpec, params: dict[str, Any]) -> BaseChatModel:
    """The single place that instantiates a provider model."""
    model_params = dict(params)
    model_params.update(guardrail_kwargs(spec, model_params.pop("guardrail", None)))
    if spec.provider == "gemini":
        model_params.setdefault("request_timeout", spec.request_timeout_seconds)
        # Retry once, in this module, under the catalog policy. The provider adapter's
        # own retries would multiply attempts and make the timeout effectively unbounded.
        model_params["max_retries"] = 0
    return init_chat_model(
        spec.model, model_provider=LANGCHAIN_PROVIDERS[spec.provider], **model_params
    )


def guardrail_kwargs(spec: ModelSpec, guardrail: dict[str, str] | None) -> dict[str, Any]:
    """Model arguments that attach a Bedrock Guardrail; empty when there is none."""
    if guardrail is None:
        return {}
    if spec.provider != "bedrock":
        raise ModelConfigError(f"guardrails only work on bedrock, not {spec.provider!r}")
    config = {
        "guardrailIdentifier": guardrail["id"],
        "guardrailVersion": guardrail["version"],
        "trace": "enabled",
    }
    return {"guardrail_config": config}


def guard_user_content(user: str, guardrail: dict[str, str] | None) -> str | list[dict[str, Any]]:
    """Split the user message so only outside text (answer, CV, job) is guard content.

    The guardrail then checks just those blocks (never our own instructions), which is what
    applies prompt-attack detection to documents too (poisoning defence).
    """
    if guardrail is None:
        return user
    blocks: list[dict[str, Any]] = []
    position = 0
    for match in _EXTERNAL_BLOCK.finditer(user):
        before = user[position : match.start(3)]
        if before:
            blocks.append({"type": "text", "text": before})
        if match.group(3):
            blocks.append({"type": "guard_content", "text": match.group(3)})
        position = match.end(3)
    rest = user[position:]
    if rest or not blocks:
        blocks.append({"type": "text", "text": rest})
    return blocks


def guardrail_intervened(response: AIMessage) -> bool:
    return response.response_metadata.get("stopReason") == GUARDRAIL_INTERVENED


def estimate_cost(spec: ModelSpec, input_tokens: int, output_tokens: int) -> float:
    cost = (
        input_tokens * spec.usd_per_mtok_input + output_tokens * spec.usd_per_mtok_output
    ) / 1_000_000
    return round(cost, 8)


def hash_input(system: str, user: str) -> str:
    """SHA-256 of the exact messages sent; same messages -> same hash (cache, consistency)."""
    canonical = json.dumps({"system": system, "user": user}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def redact_secrets(text: str) -> str:
    """Mask provider credentials from the process environment, never reading .env."""
    secrets = {value for name in CREDENTIAL_ENV_NAMES if (value := os.environ.get(name))}
    variants = {
        form for value in secrets for form in (value, quote(value, safe=""), quote_plus(value))
    }
    for value in sorted(variants, key=len, reverse=True):
        text = text.replace(value, "[REDACTED]")
    return text


def append_run_record(
    record: RunRecord,
    runs_dir: Path = DEFAULT_RUNS_DIR,
    on_record: RecordObserver | None = None,
) -> Path:
    """Append one JSON line to runs/<UTC date>_<experiment>.jsonl and return the file path."""
    runs_dir.mkdir(parents=True, exist_ok=True)
    name = f"{record.created_at.date().isoformat()}_{record.experiment or NO_EXPERIMENT}.jsonl"
    path = runs_dir / name
    line = record.model_dump_json()
    with path.open("a", encoding="utf-8") as file:
        file.write(line + "\n")
    if os.environ.get(RUNS_STDOUT_ENV) == "1":
        print(RUN_RECORD_MARKER + line, flush=True)
    if on_record is not None:
        on_record(record, path)
    return path


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


_FENCE = re.compile(r"^\s*```[a-zA-Z]*\s*\n(.*?)\n?```\s*$", re.DOTALL)


def parse_structured[T: BaseModel](raw: str, schema: type[T]) -> T:
    """Parse model text as JSON and validate it; markdown fences are stripped first.

    Raises ValueError (bad JSON) or pydantic.ValidationError (wrong shape).
    """
    fenced = _FENCE.match(raw)
    text = fenced.group(1) if fenced else raw
    return schema.model_validate(json.loads(text))


def _start(
    *,
    model: str | None,
    params: dict[str, Any] | None,
    config: ModelsConfig | None,
    chat_model: BaseChatModel | None,
) -> tuple[ModelSpec, dict[str, Any], Any]:
    """Resolve the model and wrap it with the retry policy (retries are internal)."""
    spec = resolve_model(model, config or load_models_config())
    params = dict(params or {})
    llm = chat_model or build_chat_model(spec, params)
    runnable = llm.with_retry(
        stop_after_attempt=spec.max_retries + 1,
        wait_exponential_jitter=True,
        exponential_jitter_params=RETRY_WAIT,
    )
    return spec, params, runnable


def _base_record(
    *,
    spec: ModelSpec,
    params: dict[str, Any],
    prompt_name: str,
    prompt_version: int,
    system: str,
    user: str,
    input: dict[str, Any],
    experiment: str | None,
    session_id: str | None,
) -> dict[str, Any]:
    return {
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
        "output_parsed": None,
        "json_valid_first_try": None,
        "repaired": None,
        "created_at": datetime.now(UTC),
    }


def _call(
    runnable: Any,
    messages: list[Any],
    record: dict[str, Any],
    runs_dir: Path,
    on_record: RecordObserver | None,
) -> tuple[AIMessage, int]:
    """One model call. On provider failure: write the error RunRecord and re-raise."""
    started = time.perf_counter()
    try:
        response = runnable.invoke(messages)
    except Exception as exc:
        failed = RunRecord(
            **record,
            output_raw="",
            input_tokens=0,
            output_tokens=0,
            latency_ms=_elapsed_ms(started),
            cost_usd=0.0,
            error=redact_secrets(f"{type(exc).__name__}: {exc}"),
        )
        append_run_record(failed, runs_dir, on_record)
        raise
    latency_ms = _elapsed_ms(started)
    if guardrail_intervened(response):
        blocked = RunRecord(
            **record,
            output_raw=response.text,
            input_tokens=0,
            output_tokens=0,
            latency_ms=latency_ms,
            cost_usd=0.0,
            error=f"{GUARDRAIL_INTERVENED}: {response.text}",
        )
        append_run_record(blocked, runs_dir, on_record)
        raise GuardrailBlocked(response.text)
    return response, latency_ms


def _write_success(
    *,
    spec: ModelSpec,
    record: dict[str, Any],
    responses: Sequence[AIMessage],
    latency_ms: int,
    runs_dir: Path,
    on_record: RecordObserver | None,
    error: str | None = None,
) -> None:
    """Write one RunRecord for one or more calls: tokens add up, output_raw is the last text."""
    usages = [response.usage_metadata or {} for response in responses]
    input_tokens = sum(usage.get("input_tokens", 0) for usage in usages)
    output_tokens = sum(usage.get("output_tokens", 0) for usage in usages)
    append_run_record(
        RunRecord(
            **record,
            output_raw=responses[-1].text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost_usd=estimate_cost(spec, input_tokens, output_tokens),
            error=error,
        ),
        runs_dir,
        on_record,
    )


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
    on_record: RecordObserver | None = None,
) -> str:
    """Call the model with already-rendered messages, record a RunRecord, return the text.

    ``input`` holds the (already masked) variables, saved as-is in the record.
    ``chat_model`` lets tests inject a fake model; by default it is built from the config.
    ``on_record`` receives the exact record and path after persistence (success or failure).
    """
    spec, params, runnable = _start(
        model=model, params=params, config=config, chat_model=chat_model
    )
    record = _base_record(
        spec=spec,
        params=params,
        prompt_name=prompt_name,
        prompt_version=prompt_version,
        system=system,
        user=user,
        input=input,
        experiment=experiment,
        session_id=session_id,
    )
    guarded = guard_user_content(user, params.get("guardrail"))
    messages = [SystemMessage(system), HumanMessage(guarded)]
    response, latency_ms = _call(runnable, messages, record, runs_dir, on_record)
    _write_success(
        spec=spec,
        record=record,
        responses=[response],
        latency_ms=latency_ms,
        runs_dir=runs_dir,
        on_record=on_record,
    )
    return response.text


REPAIR_INSTRUCTION = (
    "Sua resposta anterior não é válida: {error}\n"
    "Responda de novo apenas com o JSON corrigido, sem texto antes ou depois."
)


def build_repair_messages(system: str, user: str, bad_output: str, error: str) -> list[BaseMessage]:
    """Original conversation + the invalid answer + a fixed request to fix it."""
    return [
        SystemMessage(system),
        HumanMessage(user),
        AIMessage(bad_output),
        HumanMessage(REPAIR_INSTRUCTION.format(error=error)),
    ]


def _parse_error(exc: ValueError) -> str:
    """Short text for the repair request: Pydantic errors as 'loc: msg', json errors as-is."""
    return _describe(exc) if isinstance(exc, ValidationError) else str(exc)


def invoke_structured[T: BaseModel](
    *,
    output_schema: type[T],
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
    on_record: RecordObserver | None = None,
) -> T:
    """Like ``invoke`` but validates the answer against ``output_schema``.

    Invalid output gets exactly one repair call; if that fails too, a single RunRecord
    with the error is written and LLMInvalidOutputError is raised. Provider failures
    are never repaired. Tokens, cost and latency of both calls are summed in one record.
    """
    spec, params, runnable = _start(
        model=model, params=params, config=config, chat_model=chat_model
    )
    record = _base_record(
        spec=spec,
        params=params,
        prompt_name=prompt_name,
        prompt_version=prompt_version,
        system=system,
        user=user,
        input=input,
        experiment=experiment,
        session_id=session_id,
    )
    guarded = guard_user_content(user, params.get("guardrail"))
    messages: list[BaseMessage] = [SystemMessage(system), HumanMessage(guarded)]
    response, latency_ms = _call(runnable, messages, record, runs_dir, on_record)
    responses = [response]
    first_try = True
    try:
        parsed = parse_structured(response.text, output_schema)
    except ValueError as exc:  # json errors and pydantic ValidationError
        first_try = False
        repair = build_repair_messages(system, user, response.text, _parse_error(exc))
        response, repair_ms = _call(runnable, repair, record, runs_dir, on_record)
        responses.append(response)
        latency_ms += repair_ms
        try:
            parsed = parse_structured(response.text, output_schema)
        except ValueError as repair_exc:
            record.update(json_valid_first_try=False, repaired=False)
            message = f"LLMInvalidOutputError: {_parse_error(repair_exc)}"
            _write_success(
                spec=spec,
                record=record,
                responses=responses,
                latency_ms=latency_ms,
                runs_dir=runs_dir,
                on_record=on_record,
                error=redact_secrets(message),
            )
            raise LLMInvalidOutputError(message) from repair_exc
    record.update(
        output_parsed=parsed.model_dump(mode="json"),
        json_valid_first_try=first_try,
        repaired=not first_try,
    )
    _write_success(
        spec=spec,
        record=record,
        responses=responses,
        latency_ms=latency_ms,
        runs_dir=runs_dir,
        on_record=on_record,
    )
    return parsed


# ---------- Voice: Nova 2 Sonic bidirectional stream (spec 5) ----------

DEFAULT_VOICE_PATH = REPO_ROOT / "config" / "voice.yaml"
VOICE_ID_ENV = "MIA_VOICE_ID"


class SonicStream(Protocol):
    """Raw Sonic event stream: JSON events in, JSON events out. Protocol logic lives in
    mia.voice.sonic; this is only transport, so tests replace it with a fake."""

    async def send(self, event: dict[str, Any]) -> None: ...

    async def receive(self) -> dict[str, Any] | None: ...  # None = stream ended

    async def close(self) -> None: ...


def load_voice_config(
    path: Path = DEFAULT_VOICE_PATH, env: Mapping[str, str] | None = None
) -> VoiceConfig:
    """Read config/voice.yaml; MIA_VOICE_ID overrides the voice."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    voice_id = (os.environ if env is None else env).get(VOICE_ID_ENV)
    if voice_id:
        raw["voice_id"] = voice_id
    return VoiceConfig.model_validate(raw)


class _BedrockSonicStream:
    """SonicStream over aws-sdk-bedrock-runtime (InvokeModelWithBidirectionalStream)."""

    def __init__(self, stream: Any) -> None:
        self._stream = stream
        self._closed = False

    async def send(self, event: dict[str, Any]) -> None:
        from aws_sdk_bedrock_runtime.models import (
            BidirectionalInputPayloadPart,
            InvokeModelWithBidirectionalStreamInputChunk,
        )

        data = json.dumps(event, ensure_ascii=False).encode("utf-8")
        chunk = InvokeModelWithBidirectionalStreamInputChunk(
            value=BidirectionalInputPayloadPart(bytes_=data)
        )
        await self._stream.input_stream.send(chunk)

    async def receive(self) -> dict[str, Any] | None:
        while True:
            output = await self._stream.await_output()
            result = await output[1].receive()
            if result is None:
                return None
            if result.value and result.value.bytes_:
                parsed: dict[str, Any] = json.loads(result.value.bytes_.decode("utf-8"))
                return parsed

    async def close(self) -> None:
        if not self._closed:
            self._closed = True
            await self._stream.input_stream.close()


async def open_sonic_stream(config: VoiceConfig) -> SonicStream:
    """Open the bidirectional stream; credentials come from the default AWS chain."""
    from aws_sdk_bedrock_runtime.client import InvokeModelWithBidirectionalStreamOperationInput
    from langchain_aws.utils import create_aws_bedrock_runtime_client

    client = create_aws_bedrock_runtime_client(region_name=config.region)
    stream = await client.invoke_model_with_bidirectional_stream(
        InvokeModelWithBidirectionalStreamOperationInput(model_id=config.model_id)
    )
    return _BedrockSonicStream(stream)


def record_voice_run(
    *,
    config: VoiceConfig,
    prompt_name: str,
    prompt_version: int,
    session_id: str | None,
    transcript: list[dict[str, str]],
    first_audio_ms: int | None,
    duration_ms: int,
    input_tokens: int,
    output_tokens: int,
    error: str | None,
    runs_dir: Path = DEFAULT_RUNS_DIR,
    models: ModelsConfig | None = None,
) -> Path:
    """One RunRecord per voice session. Never audio: only masked transcripts and metrics."""
    ref = f"bedrock:{config.model_id}"
    catalog = models or load_models_config()
    spec = catalog.models.get(ref)
    record = RunRecord(
        run_id=uuid.uuid4().hex,
        experiment=None,
        session_id=session_id,
        prompt_name=prompt_name,
        prompt_version=prompt_version,
        provider="bedrock",
        model=config.model_id,
        params={"voice_id": config.voice_id, "first_audio_ms": first_audio_ms},
        input_hash=hash_input(prompt_name, json.dumps(transcript, ensure_ascii=False)),
        input={"transcript": transcript},
        output_raw="",
        output_parsed=None,
        json_valid_first_try=None,
        repaired=None,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=duration_ms,
        cost_usd=estimate_cost(spec, input_tokens, output_tokens) if spec else 0.0,
        error=redact_secrets(error) if error else None,
        created_at=datetime.now(UTC),
    )
    return append_run_record(record, runs_dir)
