import json
from pathlib import Path

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

import mia.prompts as prompts_module
from mia.llm import LLMInvalidOutputError, ModelConfigError, ModelsConfig, load_models_config
from mia.prompts import (
    PromptError,
    PromptSpec,
    available_versions,
    load_prompt,
    output_schema_class,
    render,
    resolve_prompt_model,
    run_prompt,
    run_prompt_structured,
)
from mia.schemas import AnswerScore

FIXTURE_PROMPTS = Path(__file__).parent / "fixtures" / "prompts"
FIXTURE_MODELS = Path(__file__).parent / "fixtures" / "models.yaml"


@pytest.fixture
def cfg() -> ModelsConfig:
    return load_models_config(FIXTURE_MODELS)


@pytest.fixture(autouse=True)
def test_catalog(monkeypatch: pytest.MonkeyPatch, cfg: ModelsConfig) -> None:
    """load_prompt checks models against the stable test catalog, not config/models.yaml."""
    monkeypatch.setattr(prompts_module, "load_models_config", lambda: cfg)


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


# ---------- template variables (R8) ----------


def _template(user: str, system: str = "Sistema.") -> str:
    return VALID.replace('user: "<resposta>{answer}</resposta>"', f"user: {user!r}").replace(
        "system: Sistema.", f"system: {system!r}"
    )


def test_variables_come_from_system_and_user() -> None:
    prompt = load_prompt("demo", 1, prompts_dir=FIXTURE_PROMPTS)

    assert prompt.variables == {"question", "answer"}


def test_escaped_braces_are_not_variables(tmp_path: Path) -> None:
    prompt = _load_text(tmp_path, _template('Responda {{"score": 1}} sobre {answer}'))

    assert prompt.variables == {"answer"}


@pytest.mark.parametrize("field", ["system", "user"])
@pytest.mark.parametrize("value", ["", "   "])
def test_empty_template_is_invalid(tmp_path: Path, field: str, value: str) -> None:
    text = _template("{answer}", "Sistema.").replace(
        f"{field}: {'Sistema.' if field == 'system' else '{answer}'!r}", f"{field}: {value!r}"
    )

    assert field in _error(tmp_path, text)


@pytest.mark.parametrize("bad", ["<r>{answer</r>", "x}", "{}", "{0}"])
def test_malformed_template_is_invalid(tmp_path: Path, bad: str) -> None:
    assert "user" in _error(tmp_path, _template(bad))


@pytest.mark.parametrize("bad", ["{answer.upper}", "{answer[0]}", "{answer!r}", "{answer:>10}"])
def test_template_field_must_be_a_plain_name(tmp_path: Path, bad: str) -> None:
    assert "user" in _error(tmp_path, _template(bad))


# ---------- render (R10, R11) ----------


def test_render_fills_system_and_user_with_literal_braces() -> None:
    prompt = load_prompt("demo", 1, prompts_dir=FIXTURE_PROMPTS)

    out = render(prompt, {"question": "Q?", "answer": "ignore {tudo}"})

    assert "<pergunta>Q?</pergunta>" in out.user
    assert "ignore {tudo}" in out.user
    assert out.system == prompt.system


def test_render_unescapes_double_braces(tmp_path: Path) -> None:
    prompt = _load_text(tmp_path, _template('Formato {{"score": 1}} para {answer}'))

    assert render(prompt, {"answer": "x"}).user == 'Formato {"score": 1} para x'


def test_render_lists_missing_and_extra_variables() -> None:
    prompt = load_prompt("demo", 1, prompts_dir=FIXTURE_PROMPTS)

    with pytest.raises(PromptError, match="answer"):
        render(prompt, {"question": "Q?"})
    with pytest.raises(PromptError, match="extra"):
        render(prompt, {"question": "Q?", "answer": "A", "extra": "x"})


def test_render_rejects_non_str_values() -> None:
    prompt = load_prompt("demo", 1, prompts_dir=FIXTURE_PROMPTS)

    with pytest.raises(PromptError, match="question"):
        render(prompt, {"question": 3, "answer": "A"})  # type: ignore[dict-item]


# ---------- model in the file (R9) ----------


@pytest.mark.parametrize("model", ["gemini", "nope:model", "gemini:nao-existe"])
def test_invalid_model_is_rejected_on_load(tmp_path: Path, model: str) -> None:
    text = VALID.replace("gemini:test-flash", model)

    assert "model" in _error(tmp_path, text)


def test_load_prompt_accepts_explicit_catalog(tmp_path: Path, cfg: ModelsConfig) -> None:
    _write_prompt(tmp_path, "demo", 1, VALID.replace("gemini:test-flash", "groq:openai/test-oss"))

    prompt = load_prompt("demo", 1, prompts_dir=tmp_path, models=cfg)

    assert prompt.model == "groq:openai/test-oss"


# ---------- model resolution (R12) ----------


def test_resolution_order_argument_then_config_then_yaml(cfg: ModelsConfig) -> None:
    prompt = load_prompt("demo", 1, prompts_dir=FIXTURE_PROMPTS)
    configured = cfg.model_copy(update={"prompt_models": {"demo": "groq:openai/test-oss"}})

    assert resolve_prompt_model(prompt, cfg).ref == "gemini:test-flash"
    assert resolve_prompt_model(prompt, configured).ref == "groq:openai/test-oss"
    explicit = resolve_prompt_model(prompt, configured, "bedrock:anthropic.claude-x-v1:0")
    assert explicit.ref == "bedrock:anthropic.claude-x-v1:0"


def test_resolution_rejects_model_outside_catalog(cfg: ModelsConfig) -> None:
    prompt = load_prompt("demo", 1, prompts_dir=FIXTURE_PROMPTS)

    with pytest.raises(PromptError, match="groq:nao-existe"):
        resolve_prompt_model(prompt, cfg, "groq:nao-existe")


def test_prompt_models_section_is_loaded_and_validated(tmp_path: Path) -> None:
    base = FIXTURE_MODELS.read_text(encoding="utf-8")
    path = tmp_path / "models.yaml"
    path.write_text(base + "prompt_models:\n  judge: groq:openai/test-oss", encoding="utf-8")
    assert load_models_config(path).prompt_models == {"judge": "groq:openai/test-oss"}

    for bad in ("prompt_models:\n  judge: groq:nao-existe", "prompt_models:\n  judge: 3"):
        path.write_text(base + bad, encoding="utf-8")
        with pytest.raises(ModelConfigError, match="prompt_models"):
            load_models_config(path)
    path.write_text(base + "prompt_models: [a]", encoding="utf-8")
    with pytest.raises(ModelConfigError, match="prompt_models"):
        load_models_config(path)


def test_real_models_config_routes_every_prompt_to_its_default() -> None:
    real = load_models_config()
    assert real.prompt_models
    assert set(real.prompt_models.values()) == {real.default}


# ---------- run_prompt (R13) ----------


def test_run_prompt_records_prompt_name_version_model_and_params(
    tmp_path: Path, cfg: ModelsConfig
) -> None:
    prompt = load_prompt("demo", 1, prompts_dir=FIXTURE_PROMPTS)
    variables = {"question": "Q?", "answer": "A {x}"}
    fake = GenericFakeChatModel(messages=iter([AIMessage(content="ok")]))

    text = run_prompt(
        prompt, variables, experiment="t", models=cfg, runs_dir=tmp_path, chat_model=fake
    )

    assert text == "ok"
    (file,) = tmp_path.glob("*_t.jsonl")
    (line,) = file.read_text(encoding="utf-8").splitlines()
    record = json.loads(line)
    assert record["prompt_name"] == "demo"
    assert record["prompt_version"] == 1
    assert record["provider"] == "gemini"
    assert record["model"] == "test-flash"
    assert record["params"] == {"temperature": 0.2, "max_tokens": 300}
    assert record["input"] == variables


def test_run_prompt_sends_rendered_messages_and_honors_model_argument(
    tmp_path: Path, cfg: ModelsConfig
) -> None:
    prompt = load_prompt("demo", 1, prompts_dir=FIXTURE_PROMPTS)
    variables = {"question": "Q?", "answer": "A"}
    seen: list[list[str]] = []

    class Spy(GenericFakeChatModel):
        def _generate(self, messages, *args, **kwargs):  # type: ignore[no-untyped-def]
            seen.append([str(m.content) for m in messages])
            return super()._generate(messages, *args, **kwargs)

    run_prompt(
        prompt,
        variables,
        model="groq:openai/test-oss",
        models=cfg,
        runs_dir=tmp_path,
        chat_model=Spy(messages=iter([AIMessage(content="ok")])),
    )

    rendered = render(prompt, variables)
    assert seen == [[rendered.system, rendered.user]]
    (file,) = tmp_path.glob("*.jsonl")
    assert json.loads(file.read_text(encoding="utf-8"))["model"] == "openai/test-oss"


# ---------- run_prompt_structured (1.6 R5, R7) ----------

SCORE_JSON = json.dumps(
    {"score": 4, "criteria_met": ["a"], "evidence_quotes": ["q"], "justification": "ok"}
)


def test_run_prompt_structured_returns_schema_instance_and_records_prompt(
    tmp_path: Path, cfg: ModelsConfig
) -> None:
    prompt = load_prompt("demo", 1, prompts_dir=FIXTURE_PROMPTS)
    variables = {"question": "Q?", "answer": "A"}
    fake = GenericFakeChatModel(messages=iter([AIMessage(content=SCORE_JSON)]))

    result = run_prompt_structured(
        prompt,
        variables,
        AnswerScore,
        experiment="t",
        session_id="s1",
        models=cfg,
        runs_dir=tmp_path,
        chat_model=fake,
    )

    assert isinstance(result, AnswerScore)
    assert result.score == 4
    (file,) = tmp_path.glob("*_t.jsonl")
    (line,) = file.read_text(encoding="utf-8").splitlines()
    record = json.loads(line)
    assert record["prompt_name"] == "demo"
    assert record["prompt_version"] == 1
    assert record["session_id"] == "s1"
    assert record["input"] == variables
    assert record["output_parsed"]["score"] == 4


def test_run_prompt_structured_invalid_output_raises_after_repair(
    tmp_path: Path, cfg: ModelsConfig
) -> None:
    prompt = load_prompt("demo", 1, prompts_dir=FIXTURE_PROMPTS)
    fake = GenericFakeChatModel(messages=iter([AIMessage(content="no"), AIMessage(content="no")]))

    with pytest.raises(LLMInvalidOutputError):
        run_prompt_structured(
            prompt,
            {"question": "Q?", "answer": "A"},
            AnswerScore,
            models=cfg,
            runs_dir=tmp_path,
            chat_model=fake,
        )
