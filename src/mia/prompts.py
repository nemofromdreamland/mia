"""Prompt library loader: reads and validates prompts/<name>/v<N>.yaml.

See docs/BACKEND_SCHEMA.md ("Prompt") and docs/TRD.md ("Prompts: biblioteca e versionamento").
"""

import re
import string
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, ValidationError

from mia import schemas
from mia.llm import (
    DEFAULT_RUNS_DIR,
    ModelConfigError,
    ModelsConfig,
    ModelSpec,
    invoke,
    invoke_structured,
    load_models_config,
    resolve_model,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROMPTS_DIR = REPO_ROOT / "prompts"

# "v1.yaml", "v12.yaml"; no leading zeros, so each version has exactly one file name.
VERSION_FILE = re.compile(r"v([1-9]\d*)\.yaml")


class PromptError(Exception):
    """A prompt file is missing or invalid."""


class _PromptFile(BaseModel):
    """Exactly the fields allowed in the YAML file."""

    model_config = ConfigDict(extra="forbid")

    name: StrictStr
    version: StrictInt = Field(ge=1)
    model: StrictStr  # "provider:model_id"
    params: dict[str, Any]
    output_schema: StrictStr | None = None  # class name in mia.schemas; None = free text
    system: StrictStr
    user: StrictStr
    changelog: StrictStr | None = None  # required from version 2 on


class PromptSpec(_PromptFile):
    """A validated prompt plus fields filled in by the loader (never by the YAML)."""

    path: Path  # source file, used in error messages
    variables: frozenset[str]  # {name} placeholders in system + user


class RenderedPrompt(BaseModel):
    system: str
    user: str


def _describe(exc: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}" for err in exc.errors()
    )


def available_versions(name: str, prompts_dir: Path = DEFAULT_PROMPTS_DIR) -> list[int]:
    """Version numbers of prompts_dir/<name>/v<N>.yaml, sorted; other files are ignored."""
    folder = prompts_dir / name
    if not folder.is_dir():
        return []
    matches = (VERSION_FILE.fullmatch(path.name) for path in folder.iterdir())
    return sorted(int(match.group(1)) for match in matches if match)


def _schema_class(name: str) -> type[BaseModel] | None:
    """The BaseModel subclass defined in mia.schemas with this name, or None."""
    candidate = getattr(schemas, name, None)
    if (
        isinstance(candidate, type)
        and issubclass(candidate, BaseModel)
        and candidate.__module__ == schemas.__name__
    ):
        return candidate
    return None


def output_schema_class(prompt: PromptSpec) -> type[BaseModel] | None:
    """The schema class the prompt's output must follow; None for free-text prompts."""
    if prompt.output_schema is None:
        return None
    return _schema_class(prompt.output_schema)


def _read_yaml(path: Path, name: str) -> dict[str, Any]:
    if not path.is_file():
        versions = available_versions(name, path.parent.parent)
        listed = ", ".join(str(v) for v in versions) or "none"
        raise PromptError(f"{path}: prompt file not found (available versions: {listed})")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise PromptError(f"{path}: cannot read prompt file ({exc})") from exc
    if not isinstance(raw, dict):
        raise PromptError(f"{path}: prompt file must be a mapping of fields")
    return raw


def _check_consistency(spec: _PromptFile, name: str, version: int, path: Path) -> None:
    if spec.name != name:
        raise PromptError(f"{path}: name: {spec.name!r} does not match folder {name!r}")
    if spec.version != version:
        raise PromptError(
            f"{path}: version: {spec.version} does not match file name v{version}.yaml"
        )
    if spec.output_schema is not None and _schema_class(spec.output_schema) is None:
        raise PromptError(
            f"{path}: output_schema: {spec.output_schema!r} is not a model in mia.schemas"
        )
    if spec.version >= 2 and not (spec.changelog and spec.changelog.strip()):
        raise PromptError(f"{path}: changelog: required from version 2 on")


def _check_model(ref: str, models: ModelsConfig, path: Path) -> None:
    try:
        resolve_model(ref, models)
    except ModelConfigError as exc:
        raise PromptError(f"{path}: model: {exc}") from exc


def _template_variables(path: Path, field: str, template: str) -> set[str]:
    """Placeholder names in a template. Only plain {name} is allowed; {{ }} is a literal brace.

    Attribute access ({a.b}), indexing ({a[0]}), conversions ({a!r}) and format specs
    ({a:>10}) are rejected so a template can never reach into the values.
    """
    if not template.strip():
        raise PromptError(f"{path}: {field}: must not be empty")
    try:
        parsed = list(string.Formatter().parse(template))
    except ValueError as exc:
        raise PromptError(f"{path}: {field}: malformed template ({exc})") from exc
    names: set[str] = set()
    for _, name, spec, conversion in parsed:
        if name is None:
            continue
        if not name.isidentifier() or spec or conversion:
            raise PromptError(f"{path}: {field}: only plain {{name}} fields are allowed")
        names.add(name)
    return names


def load_prompt(
    name: str,
    version: int,
    *,
    prompts_dir: Path = DEFAULT_PROMPTS_DIR,
    models: ModelsConfig | None = None,
) -> PromptSpec:
    """Read and validate prompts_dir/<name>/v<version>.yaml (models: catalog, default = config)."""
    path = prompts_dir / name / f"v{version}.yaml"
    raw = _read_yaml(path, name)
    try:
        spec = _PromptFile.model_validate(raw)
    except ValidationError as exc:
        raise PromptError(f"{path}: {_describe(exc)}") from exc
    _check_consistency(spec, name, version, path)
    _check_model(spec.model, models or load_models_config(), path)
    variables = _template_variables(path, "system", spec.system) | _template_variables(
        path, "user", spec.user
    )
    return PromptSpec(**spec.model_dump(), path=path, variables=frozenset(variables))


def render(prompt: PromptSpec, variables: Mapping[str, str]) -> RenderedPrompt:
    """Fill system and user. Values are inserted as text, even if they contain braces."""
    bad = sorted(k for k, v in variables.items() if not isinstance(v, str))
    if bad:
        raise PromptError(f"{prompt.path}: variables must be str: {', '.join(bad)}")
    missing = sorted(prompt.variables - variables.keys())
    extra = sorted(variables.keys() - prompt.variables)
    if missing or extra:
        parts = [f"missing: {', '.join(missing)}"] if missing else []
        parts += [f"unexpected: {', '.join(extra)}"] if extra else []
        raise PromptError(f"{prompt.path}: variables {'; '.join(parts)}")
    values = dict(variables)
    return RenderedPrompt(
        system=prompt.system.format_map(values), user=prompt.user.format_map(values)
    )


def resolve_prompt_model(
    prompt: PromptSpec, models: ModelsConfig, override: str | None = None
) -> ModelSpec:
    """Model for this prompt: explicit argument > prompt_models in config > model in the YAML."""
    ref = override or models.prompt_models.get(prompt.name) or prompt.model
    try:
        return resolve_model(ref, models)
    except ModelConfigError as exc:
        raise PromptError(f"{prompt.path}: model: {exc}") from exc


def run_prompt(
    prompt: PromptSpec,
    variables: Mapping[str, str],
    *,
    model: str | None = None,
    experiment: str | None = None,
    session_id: str | None = None,
    models: ModelsConfig | None = None,
    runs_dir: Path = DEFAULT_RUNS_DIR,
    chat_model: BaseChatModel | None = None,
    params: dict[str, Any] | None = None,
) -> str:
    """Render the prompt and call llm.invoke; the RunRecord gets its name, version and params.

    variables must already be PII-masked. The reply is returned as text (no validation here).
    """
    models = models or load_models_config()
    rendered = render(prompt, variables)
    spec = resolve_prompt_model(prompt, models, model)
    return invoke(
        prompt_name=prompt.name,
        prompt_version=prompt.version,
        system=rendered.system,
        user=rendered.user,
        input=dict(variables),
        model=spec.ref,
        params={**prompt.params, **(params or {})},
        experiment=experiment,
        session_id=session_id,
        config=models,
        runs_dir=runs_dir,
        chat_model=chat_model,
    )


def run_prompt_structured[T: BaseModel](
    prompt: PromptSpec,
    variables: Mapping[str, str],
    output_schema: type[T],
    *,
    model: str | None = None,
    experiment: str | None = None,
    session_id: str | None = None,
    models: ModelsConfig | None = None,
    runs_dir: Path = DEFAULT_RUNS_DIR,
    chat_model: BaseChatModel | None = None,
    params: dict[str, Any] | None = None,
) -> T:
    """Like run_prompt, but the reply is validated against output_schema (one repair try).

    variables must already be PII-masked. Raises LLMInvalidOutputError if the repair fails too.
    """
    models = models or load_models_config()
    rendered = render(prompt, variables)
    spec = resolve_prompt_model(prompt, models, model)
    return invoke_structured(
        output_schema=output_schema,
        prompt_name=prompt.name,
        prompt_version=prompt.version,
        system=rendered.system,
        user=rendered.user,
        input=dict(variables),
        model=spec.ref,
        params={**prompt.params, **(params or {})},
        experiment=experiment,
        session_id=session_id,
        config=models,
        runs_dir=runs_dir,
        chat_model=chat_model,
    )
