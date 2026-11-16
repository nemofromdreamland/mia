"""Prompt library loader: reads and validates prompts/<name>/v<N>.yaml.

See docs/BACKEND_SCHEMA.md ("Prompt") and docs/TRD.md ("Prompts: biblioteca e versionamento").
"""

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, ValidationError

from mia import schemas

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


def load_prompt(
    name: str,
    version: int,
    *,
    prompts_dir: Path = DEFAULT_PROMPTS_DIR,
) -> PromptSpec:
    """Read and validate prompts_dir/<name>/v<version>.yaml."""
    path = prompts_dir / name / f"v{version}.yaml"
    raw = _read_yaml(path, name)
    try:
        spec = _PromptFile.model_validate(raw)
    except ValidationError as exc:
        raise PromptError(f"{path}: {_describe(exc)}") from exc
    _check_consistency(spec, name, version, path)
    return PromptSpec(**spec.model_dump(), path=path)
