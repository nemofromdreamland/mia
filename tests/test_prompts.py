from pathlib import Path

import pytest

from mia.prompts import (
    PromptError,
    PromptSpec,
    available_versions,
    load_prompt,
    output_schema_class,
)
from mia.schemas import AnswerScore

FIXTURE_PROMPTS = Path(__file__).parent / "fixtures" / "prompts"

VALID = """\
name: demo
version: 1
model: "gemini:test-flash"
params: {temperature: 0.2}
system: Sistema.
user: "<resposta>{answer}</resposta>"
"""


def _write_prompt(prompts_dir: Path, name: str, version: int, text: str) -> Path:
    path = prompts_dir / name / f"v{version}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _load_text(tmp_path: Path, text: str, name: str = "demo", version: int = 1) -> PromptSpec:
    _write_prompt(tmp_path, name, version, text)
    return load_prompt(name, version, prompts_dir=tmp_path)


def _error(tmp_path: Path, text: str, name: str = "demo", version: int = 1) -> str:
    with pytest.raises(PromptError) as exc:
        _load_text(tmp_path, text, name, version)
    return str(exc.value)


# ---------- happy path (R1, R6) ----------


def test_load_valid_prompt_returns_all_fields() -> None:
    prompt = load_prompt("demo", 1, prompts_dir=FIXTURE_PROMPTS)

    assert prompt.name == "demo"
    assert prompt.version == 1
    assert prompt.model == "gemini:test-flash"
    assert prompt.params == {"temperature": 0.2, "max_tokens": 300}
    assert prompt.output_schema == "AnswerScore"
    assert prompt.system.startswith("Você avalia")
    assert "<resposta>{answer}</resposta>" in prompt.user
    assert prompt.changelog is None
    assert prompt.path == FIXTURE_PROMPTS / "demo" / "v1.yaml"
    assert output_schema_class(prompt) is AnswerScore


def test_free_text_prompt_has_no_output_schema() -> None:
    prompt = load_prompt("free", 1, prompts_dir=FIXTURE_PROMPTS)

    assert prompt.output_schema is None
    assert output_schema_class(prompt) is None


def test_v2_with_changelog_loads() -> None:
    prompt = load_prompt("demo", 2, prompts_dir=FIXTURE_PROMPTS)

    assert prompt.version == 2
    assert prompt.changelog == "Temperatura zero para respostas mais estáveis"


def test_available_versions_lists_sorted_numbers_and_ignores_other_files(
    tmp_path: Path,
) -> None:
    for version in (10, 2, 1):
        _write_prompt(tmp_path, "demo", version, VALID)
    for junk in ("v01.yaml", "v3.yml", "notes.yaml", "vx.yaml"):
        (tmp_path / "demo" / junk).write_text("x", encoding="utf-8")

    assert available_versions("demo", tmp_path) == [1, 2, 10]
    assert available_versions("nothing", tmp_path) == []


# ---------- file errors (R2, R3) ----------


def test_missing_version_lists_available_ones() -> None:
    with pytest.raises(PromptError) as exc:
        load_prompt("demo", 9, prompts_dir=FIXTURE_PROMPTS)

    message = str(exc.value)
    assert "v9.yaml" in message
    assert "available versions: 1, 2" in message


def test_missing_prompt_says_none_available(tmp_path: Path) -> None:
    with pytest.raises(PromptError) as exc:
        load_prompt("nothing", 1, prompts_dir=tmp_path)

    assert "available versions: none" in str(exc.value)


def test_invalid_yaml_is_error_with_path(tmp_path: Path) -> None:
    message = _error(tmp_path, ": [")

    assert "v1.yaml" in message
    assert "cannot read" in message


def test_yaml_that_is_not_a_mapping_is_error(tmp_path: Path) -> None:
    message = _error(tmp_path, "- a\n- b\n")

    assert "v1.yaml" in message
    assert "mapping" in message


# ---------- field errors (R4) ----------


def test_missing_required_field_is_named(tmp_path: Path) -> None:
    text = VALID.replace('user: "<resposta>{answer}</resposta>"\n', "")

    message = _error(tmp_path, text)

    assert "v1.yaml" in message
    assert "user" in message


def test_unknown_field_is_named(tmp_path: Path) -> None:
    message = _error(tmp_path, VALID + "temperatura: 0.2\n")

    assert "temperatura" in message


@pytest.mark.parametrize("field", ["path", "variables"])
def test_loader_fields_cannot_come_from_yaml(tmp_path: Path, field: str) -> None:
    message = _error(tmp_path, VALID + f"{field}: x\n")

    assert field in message


@pytest.mark.parametrize(
    ("old", "new", "field"),
    [
        ("version: 1", 'version: "1"', "version"),
        ("version: 1", "version: 0", "version"),
        ("params: {temperature: 0.2}", "params: []", "params"),
        ('model: "gemini:test-flash"', "model: 3", "model"),
        ("system: Sistema.", "system: [a]", "system"),
    ],
)
def test_wrong_type_is_named(tmp_path: Path, old: str, new: str, field: str) -> None:
    message = _error(tmp_path, VALID.replace(old, new))

    assert field in message


# ---------- name/version consistency (R5) ----------


def test_name_must_match_folder(tmp_path: Path) -> None:
    message = _error(tmp_path, VALID.replace("name: demo", "name: outro"))

    assert "outro" in message
    assert "demo" in message


def test_version_must_match_file_name(tmp_path: Path) -> None:
    text = VALID.replace("version: 1", "version: 2") + 'changelog: "x"\n'

    message = _error(tmp_path, text, version=1)

    assert "version" in message
    assert "2" in message
    assert "v1.yaml" in message


# ---------- output_schema (R6) ----------


@pytest.mark.parametrize("schema", ["Nada", "Literal", "BaseModel", "Persona"])
def test_output_schema_must_be_a_model_from_schemas(tmp_path: Path, schema: str) -> None:
    message = _error(tmp_path, VALID + f"output_schema: {schema}\n")

    assert "output_schema" in message
    assert schema in message


# ---------- changelog (R7) ----------


@pytest.mark.parametrize("changelog", ["", 'changelog: ""\n', 'changelog: "   "\n'])
def test_v2_requires_changelog(tmp_path: Path, changelog: str) -> None:
    text = VALID.replace("version: 1", "version: 2") + changelog

    message = _error(tmp_path, text, version=2)

    assert "changelog" in message


def test_v1_does_not_require_changelog(tmp_path: Path) -> None:
    assert _load_text(tmp_path, VALID).changelog is None


def test_non_text_yaml_key_is_error_not_crash(tmp_path: Path) -> None:
    message = _error(tmp_path, VALID + "1: x\n")

    assert "1" in message
