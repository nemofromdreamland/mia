from pathlib import Path
from typing import Any

import pytest

import mia.llm as llm
from mia.llm import (
    ModelConfigError,
    ModelsConfig,
    build_chat_model,
    estimate_cost,
    load_models_config,
    resolve_model,
)

FIXTURE_MODELS = Path(__file__).parent / "fixtures" / "models.yaml"
SRC_DIR = Path(__file__).parents[1] / "src" / "mia"


@pytest.fixture
def cfg() -> ModelsConfig:
    return load_models_config(FIXTURE_MODELS)


def _write_config(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "models.yaml"
    path.write_text(text, encoding="utf-8")
    return path


# --- load_models_config (R2) -------------------------------------------------


def test_load_models_config_reads_default_and_catalog(cfg: ModelsConfig) -> None:
    assert cfg.default == "gemini:test-flash"
    flash = cfg.models["gemini:test-flash"]
    assert flash.provider == "gemini"
    assert flash.model == "test-flash"
    assert flash.free_tier is True
    assert cfg.models["bedrock:anthropic.claude-x-v1:0"].free_tier is False


def test_load_models_config_splits_ref_on_first_colon_only(cfg: ModelsConfig) -> None:
    spec = cfg.models["bedrock:anthropic.claude-x-v1:0"]

    assert spec.provider == "bedrock"
    assert spec.model == "anthropic.claude-x-v1:0"


def test_load_models_config_rejects_negative_price_naming_file_and_field(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        'default: "gemini:x"\n'
        "models:\n"
        '  "gemini:x": {usd_per_mtok_input: -1, usd_per_mtok_output: 0.4}\n',
    )

    with pytest.raises(ModelConfigError) as exc_info:
        load_models_config(path)

    message = str(exc_info.value)
    assert str(path) in message
    assert "usd_per_mtok_input" in message


def test_load_models_config_rejects_missing_price(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        'default: "gemini:x"\nmodels:\n  "gemini:x": {usd_per_mtok_input: 0.1}\n',
    )

    with pytest.raises(ModelConfigError, match="usd_per_mtok_output"):
        load_models_config(path)


def test_load_models_config_rejects_unknown_provider(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        'default: "openai:gpt-x"\n'
        "models:\n"
        '  "openai:gpt-x": {usd_per_mtok_input: 1, usd_per_mtok_output: 2}\n',
    )

    with pytest.raises(ModelConfigError, match="openai"):
        load_models_config(path)


def test_load_models_config_rejects_default_outside_catalog(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        'default: "groq:nao-existe"\n'
        "models:\n"
        '  "gemini:x": {usd_per_mtok_input: 1, usd_per_mtok_output: 2}\n',
    )

    with pytest.raises(ModelConfigError, match="groq:nao-existe"):
        load_models_config(path)


def test_load_models_config_rejects_file_without_models_mapping(tmp_path: Path) -> None:
    path = _write_config(tmp_path, 'default: "gemini:x"\n')

    with pytest.raises(ModelConfigError, match="models"):
        load_models_config(path)


def test_load_models_config_rejects_entry_that_is_not_a_mapping(tmp_path: Path) -> None:
    path = _write_config(tmp_path, 'default: "gemini:x"\nmodels:\n  "gemini:x": 0.1\n')

    with pytest.raises(ModelConfigError, match="gemini:x"):
        load_models_config(path)


def test_load_models_config_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ModelConfigError, match="nao_existe.yaml"):
        load_models_config(tmp_path / "nao_existe.yaml")


def test_real_models_config_loads_with_free_tier_on_gemini_and_groq() -> None:
    real = load_models_config()

    assert real.default.startswith("gemini:")
    free = {spec.provider for spec in real.models.values() if spec.free_tier}
    paid = {spec.provider for spec in real.models.values() if not spec.free_tier}
    assert free == {"gemini", "groq"}
    assert paid == {"bedrock"}


# --- resolve_model (R3) ------------------------------------------------------


def test_resolve_model_returns_spec_and_none_means_default(cfg: ModelsConfig) -> None:
    assert resolve_model("gemini:test-flash", cfg) is cfg.models["gemini:test-flash"]
    assert resolve_model(None, cfg) is cfg.models["gemini:test-flash"]


@pytest.mark.parametrize("ref", ["gemini:nao-existe", "semdoispontos", ":vazio", "gemini:"])
def test_resolve_model_rejects_unknown_or_malformed_ref(cfg: ModelsConfig, ref: str) -> None:
    with pytest.raises(ModelConfigError):
        resolve_model(ref, cfg)


# --- estimate_cost -----------------------------------------------------------


def test_estimate_cost_uses_price_per_million_tokens(cfg: ModelsConfig) -> None:
    spec = cfg.models["gemini:test-flash"]

    assert estimate_cost(spec, 1_000_000, 500_000) == pytest.approx(0.30)
    assert estimate_cost(spec, 0, 0) == 0.0


# --- build_chat_model (R4) ---------------------------------------------------


@pytest.mark.parametrize(
    ("ref", "expected_model", "expected_provider"),
    [
        ("bedrock:anthropic.claude-x-v1:0", "anthropic.claude-x-v1:0", "bedrock_converse"),
        ("gemini:test-flash", "test-flash", "google_genai"),
        ("groq:openai/test-oss", "openai/test-oss", "groq"),
    ],
)
def test_build_chat_model_calls_init_chat_model_with_langchain_provider(
    cfg: ModelsConfig,
    monkeypatch: pytest.MonkeyPatch,
    ref: str,
    expected_model: str,
    expected_provider: str,
) -> None:
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    sentinel = object()

    def fake_init_chat_model(*args: Any, **kwargs: Any) -> object:
        calls.append((args, kwargs))
        return sentinel

    monkeypatch.setattr(llm, "init_chat_model", fake_init_chat_model)

    result = build_chat_model(cfg.models[ref], {"temperature": 0.2})

    assert result is sentinel
    assert calls == [((expected_model,), {"model_provider": expected_provider, "temperature": 0.2})]


def test_only_llm_module_touches_langchain_models_or_provider_packages() -> None:
    forbidden = ("init_chat_model", "langchain_aws", "langchain_google", "langchain_groq")
    offenders = [
        path.name
        for path in SRC_DIR.rglob("*.py")
        if path.name != "llm.py" and any(word in path.read_text("utf-8") for word in forbidden)
    ]

    assert offenders == []
