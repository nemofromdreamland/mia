import importlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatResult

import mia.llm as llm
from mia.llm import (
    ModelConfigError,
    ModelsConfig,
    build_chat_model,
    estimate_cost,
    hash_input,
    invoke,
    load_models_config,
    resolve_model,
)
from mia.schemas import RunRecord

FIXTURE_MODELS = Path(__file__).parent / "fixtures" / "models.yaml"
SRC_DIR = Path(__file__).parents[1] / "src" / "mia"


@pytest.fixture
def cfg() -> ModelsConfig:
    return load_models_config(FIXTURE_MODELS)


@pytest.fixture(autouse=True)
def no_retry_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    """Retries happen instantly in tests (no sleeping between attempts)."""
    monkeypatch.setattr(llm, "RETRY_WAIT", {"initial": 0, "max": 0, "jitter": 0})


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


@pytest.mark.parametrize(
    ("fields", "field"),
    [
        ("model: x, usd_per_mtok_input: 0.1", "model"),
        ("provider: gemini, usd_per_mtok_input: -1, usd_per_mtok_output: 0.4", "provider"),
        ("ref: 'gemini:x', usd_per_mtok_input: 0.1, usd_per_mtok_output: 0.4", "ref"),
    ],
)
def test_load_models_config_rejects_derived_fields(tmp_path: Path, fields: str, field: str) -> None:
    path = _write_config(tmp_path, f'default: "gemini:x"\nmodels:\n  "gemini:x": {{{fields}}}\n')

    with pytest.raises(ModelConfigError) as exc_info:
        load_models_config(path)

    assert str(path) in str(exc_info.value)
    assert f"models.gemini:x.{field}" in str(exc_info.value)


@pytest.mark.parametrize("default", ['["gemini:x"]', '{model: "gemini:x"}', "123", "null"])
def test_load_models_config_rejects_non_string_default(tmp_path: Path, default: str) -> None:
    path = _write_config(
        tmp_path,
        f"default: {default}\nmodels:\n"
        '  "gemini:x": {usd_per_mtok_input: 0.1, usd_per_mtok_output: 0.4}\n',
    )

    with pytest.raises(ModelConfigError) as exc_info:
        load_models_config(path)

    assert str(path) in str(exc_info.value)
    assert "default" in str(exc_info.value)


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


def test_real_models_config_uses_haiku_geo_pricing() -> None:
    # Anthropic list prices effective 2026-11-09: Geo Cross Region, not Global.
    spec = load_models_config().models["bedrock:us.anthropic.claude-haiku-4-5-20251001-v1:0"]

    assert estimate_cost(spec, 1_000_000, 0) == pytest.approx(1.10)
    assert estimate_cost(spec, 0, 1_000_000) == pytest.approx(5.50)


@pytest.mark.parametrize(
    ("ref", "usd_in", "usd_out"),
    [
        # Bare Nova id has no on-demand access in us-east-1; "us." profile = in-region price.
        ("bedrock:us.amazon.nova-2-lite-v1:0", 0.33, 2.75),
        # gemini-2.5-flash is gone for new users; 3.8 Flash promotional rate until 2026-12-31.
        ("gemini:gemini-3.8-flash", 0.75, 3.75),
    ],
)
def test_real_models_config_uses_ids_and_prices_confirmed_in_smoke_test(
    ref: str, usd_in: float, usd_out: float
) -> None:
    spec = load_models_config().models[ref]

    assert estimate_cost(spec, 1_000_000, 0) == pytest.approx(usd_in)
    assert estimate_cost(spec, 0, 1_000_000) == pytest.approx(usd_out)


# --- max_retries (0.6 R1) ----------------------------------------------------


def test_max_retries_defaults_to_two_and_reads_explicit_value(cfg: ModelsConfig) -> None:
    assert cfg.models["gemini:test-flash"].max_retries == 2
    assert cfg.models["groq:openai/test-oss"].max_retries == 4


@pytest.mark.parametrize("value", ["-1", '"x"', "1.5"])
def test_max_retries_rejects_invalid_value_naming_file_and_field(
    tmp_path: Path, value: str
) -> None:
    path = _write_config(
        tmp_path,
        'default: "gemini:x"\nmodels:\n'
        '  "gemini:x": {usd_per_mtok_input: 0.1, usd_per_mtok_output: 0.4, '
        f"max_retries: {value}}}\n",
    )

    with pytest.raises(ModelConfigError) as exc_info:
        load_models_config(path)

    assert str(path) in str(exc_info.value)
    assert "max_retries" in str(exc_info.value)


def test_real_models_config_gives_groq_more_retries() -> None:
    assert load_models_config().models["groq:openai/gpt-oss-120b"].max_retries == 4


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


@pytest.mark.parametrize(
    ("ref", "class_path"),
    [
        ("bedrock:anthropic.claude-x-v1:0", "langchain_aws.ChatBedrockConverse"),
        ("gemini:test-flash", "langchain_google_genai.ChatGoogleGenerativeAI"),
        ("groq:openai/test-oss", "langchain_groq.ChatGroq"),
    ],
)
def test_build_chat_model_returns_real_class_for_provider_without_network(
    cfg: ModelsConfig, monkeypatch: pytest.MonkeyPatch, ref: str, class_path: str
) -> None:
    # Fake credentials only: building a client must not call the provider.
    for name, value in {
        "GOOGLE_API_KEY": "fake-google",
        "GROQ_API_KEY": "fake-groq",
        "AWS_ACCESS_KEY_ID": "fake-id",
        "AWS_SECRET_ACCESS_KEY": "fake-secret",
        "AWS_REGION": "us-east-1",
        "AWS_DEFAULT_REGION": "us-east-1",
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    module_name, class_name = class_path.rsplit(".", 1)
    expected = getattr(importlib.import_module(module_name), class_name)

    assert isinstance(build_chat_model(cfg.models[ref], {"temperature": 0}), expected)


def test_only_llm_module_touches_langchain_models_or_provider_packages() -> None:
    forbidden = ("init_chat_model", "langchain_aws", "langchain_google", "langchain_groq")
    offenders = [
        path.name
        for path in SRC_DIR.rglob("*.py")
        if path.name != "llm.py" and any(word in path.read_text("utf-8") for word in forbidden)
    ]

    assert offenders == []


# --- invoke + RunRecord (R5-R9) ----------------------------------------------


class _FailingChatModel(GenericFakeChatModel):
    """Fake provider that blows up on every call."""

    def _generate(self, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("boom")


class _FlakyChatModel(GenericFakeChatModel):
    """Fake provider that fails the first `failures` calls, then answers."""

    failures: int = 0
    message: str = "boom"
    calls: int = 0

    def _generate(self, *args: Any, **kwargs: Any) -> Any:
        self.calls += 1
        if self.calls <= self.failures:
            raise RuntimeError(self.message)
        return super()._generate(*args, **kwargs)


def _fake_model(*replies: str | AIMessage) -> GenericFakeChatModel:
    return GenericFakeChatModel(messages=iter(replies))


def _reply(text: str, input_tokens: int = 12, output_tokens: int = 3) -> AIMessage:
    return AIMessage(
        content=text,
        usage_metadata={
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        },
    )


def _today_file(runs_dir: Path, experiment: str) -> Path:
    return runs_dir / f"{datetime.now(UTC).date().isoformat()}_{experiment}.jsonl"


def _read_records(path: Path) -> list[RunRecord]:
    return [RunRecord.model_validate_json(line) for line in path.read_text("utf-8").splitlines()]


def _invoke(cfg: ModelsConfig, runs_dir: Path, chat_model: Any, **overrides: Any) -> str:
    kwargs: dict[str, Any] = {
        "prompt_name": "smoke",
        "prompt_version": 1,
        "system": "s",
        "user": "u",
        "input": {"q": "u"},
        "experiment": "test",
        "config": cfg,
        "runs_dir": runs_dir,
        "chat_model": chat_model,
    }
    kwargs.update(overrides)
    return invoke(**kwargs)


def test_invoke_returns_text_and_writes_one_valid_run_record(
    cfg: ModelsConfig, tmp_path: Path
) -> None:
    before = datetime.now(UTC)

    text = _invoke(
        cfg,
        tmp_path,
        _fake_model(_reply("olá")),
        params={"temperature": 0.2},
        session_id="01JCASE0000000000000000000",
    )

    assert text == "olá"
    records = _read_records(_today_file(tmp_path, "test"))
    assert len(records) == 1
    record = records[0]
    assert record.prompt_name == "smoke"
    assert record.prompt_version == 1
    assert record.experiment == "test"
    assert record.session_id == "01JCASE0000000000000000000"
    assert record.provider == "gemini"
    assert record.model == "test-flash"
    assert record.params == {"temperature": 0.2}
    assert record.input == {"q": "u"}
    assert record.input_hash == hash_input("s", "u")
    assert record.output_raw == "olá"
    assert record.output_parsed is None
    assert record.json_valid_first_try is None
    assert record.repaired is None
    assert (record.input_tokens, record.output_tokens) == (12, 3)
    # free_tier model: the reference (paid) price is still recorded
    assert record.cost_usd == pytest.approx(12 * 0.10 / 1e6 + 3 * 0.40 / 1e6)
    assert record.error is None
    assert record.latency_ms >= 0
    assert record.created_at.utcoffset() == timedelta(0)
    assert before <= record.created_at <= datetime.now(UTC)


def test_invoke_same_input_same_hash_new_run_id_each_call(
    cfg: ModelsConfig, tmp_path: Path
) -> None:
    model = _fake_model(_reply("a"), _reply("b"), _reply("c"))

    _invoke(cfg, tmp_path, model)
    _invoke(cfg, tmp_path, model)
    _invoke(cfg, tmp_path, model, user="outra pergunta")

    first, second, third = _read_records(_today_file(tmp_path, "test"))
    assert first.input_hash == second.input_hash
    assert first.run_id != second.run_id
    assert third.input_hash != first.input_hash


def test_invoke_sends_exact_messages_in_role_order(
    cfg: ModelsConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[BaseMessage]] = []
    original_generate = GenericFakeChatModel._generate

    def capture(
        self: GenericFakeChatModel, messages: list[BaseMessage], **kwargs: Any
    ) -> ChatResult:
        calls.append(messages)
        return original_generate(self, messages, **kwargs)

    monkeypatch.setattr(GenericFakeChatModel, "_generate", capture)
    _invoke(cfg, tmp_path, _fake_model("ok"), system="system instructions", user="user data")

    assert calls == [[SystemMessage("system instructions"), HumanMessage("user data")]]


@pytest.mark.parametrize("fails", [False, True])
def test_invoke_records_measured_latency(
    cfg: ModelsConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fails: bool
) -> None:
    # Replace only mia.llm's clock, so LangChain's own timing does not consume our ticks.
    class Clock:
        ticks = iter([10.0, 10.125])

        @staticmethod
        def perf_counter() -> float:
            return next(Clock.ticks)

    monkeypatch.setattr(llm, "time", Clock)
    if fails:
        with pytest.raises(RuntimeError, match="boom"):
            _invoke(cfg, tmp_path, _FailingChatModel(messages=iter([])))
    else:
        _invoke(cfg, tmp_path, _fake_model("ok"))

    (record,) = _read_records(_today_file(tmp_path, "test"))
    assert record.latency_ms == 125


def test_hash_input_does_not_confuse_system_and_user_boundaries() -> None:
    assert hash_input("ab", "c") != hash_input("a", "bc")
    assert len(hash_input("s", "u")) == 64


def test_invoke_records_provider_error_and_reraises(cfg: ModelsConfig, tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="boom"):
        _invoke(cfg, tmp_path, _FailingChatModel(messages=iter([])))

    (record,) = _read_records(_today_file(tmp_path, "test"))
    assert record.error == "RuntimeError: boom"
    assert record.output_raw == ""
    assert (record.input_tokens, record.output_tokens, record.cost_usd) == (0, 0, 0.0)
    assert record.latency_ms >= 0


def test_invoke_appends_and_creates_missing_runs_dir(cfg: ModelsConfig, tmp_path: Path) -> None:
    runs_dir = tmp_path / "novo"
    model = _fake_model(_reply("a"), _reply("b"))

    _invoke(cfg, runs_dir, model)
    _invoke(cfg, runs_dir, model)

    assert [r.output_raw for r in _read_records(_today_file(runs_dir, "test"))] == ["a", "b"]


def test_invoke_without_experiment_writes_adhoc_file(cfg: ModelsConfig, tmp_path: Path) -> None:
    _invoke(cfg, tmp_path, _fake_model(_reply("a")), experiment=None)

    (record,) = _read_records(_today_file(tmp_path, "adhoc"))
    assert record.experiment is None


def test_invoke_without_usage_metadata_records_zero_tokens(
    cfg: ModelsConfig, tmp_path: Path
) -> None:
    _invoke(cfg, tmp_path, _fake_model("sem uso"))

    (record,) = _read_records(_today_file(tmp_path, "test"))
    assert (record.input_tokens, record.output_tokens, record.cost_usd) == (0, 0, 0.0)


def test_invoke_defaults_load_real_config_and_build_model_from_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    built: list[tuple[str, dict[str, Any]]] = []

    def fake_init_chat_model(model: str, **kwargs: Any) -> GenericFakeChatModel:
        built.append((model, kwargs))
        return _fake_model(_reply("ok", 1000, 1000))

    monkeypatch.setattr(llm, "init_chat_model", fake_init_chat_model)

    text = invoke(
        prompt_name="smoke",
        prompt_version=1,
        system="s",
        user="u",
        input={},
        params={"temperature": 0},
        runs_dir=tmp_path,
    )

    real = load_models_config()
    default = real.models[real.default]
    assert text == "ok"
    assert built == [(default.model, {"model_provider": "google_genai", "temperature": 0})]
    (record,) = _read_records(_today_file(tmp_path, "adhoc"))
    assert record.cost_usd == estimate_cost(default, 1000, 1000)


# --- retry (0.6 R2, R3) ------------------------------------------------------


def test_invoke_retries_then_succeeds_with_a_single_success_record(
    cfg: ModelsConfig, tmp_path: Path
) -> None:
    model = _FlakyChatModel(messages=iter([_reply("ok")]), failures=1, message="429")

    text = _invoke(cfg, tmp_path, model)

    assert text == "ok"
    assert model.calls == 2
    (record,) = _read_records(_today_file(tmp_path, "test"))
    assert record.error is None
    assert record.output_raw == "ok"


def test_invoke_retry_latency_includes_the_waits(
    cfg: ModelsConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Clock:
        ticks = iter([10.0, 12.5])  # start, end: 2.5 s around the whole retried call

        @staticmethod
        def perf_counter() -> float:
            return next(Clock.ticks)

    monkeypatch.setattr(llm, "time", Clock)
    _invoke(cfg, tmp_path, _FlakyChatModel(messages=iter([_reply("ok")]), failures=1))

    (record,) = _read_records(_today_file(tmp_path, "test"))
    assert record.latency_ms == 2500


@pytest.mark.parametrize(
    ("ref", "expected_calls"),
    [("gemini:test-flash", 3), ("groq:openai/test-oss", 5)],  # max_retries 2 and 4
)
def test_invoke_gives_up_after_max_retries_and_records_last_error(
    cfg: ModelsConfig,
    tmp_path: Path,
    ref: str,
    expected_calls: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    errors: list[RuntimeError] = []

    def fail(*args: Any, **kwargs: Any) -> Any:
        error = RuntimeError(f"attempt {len(errors) + 1}")
        errors.append(error)
        raise error

    monkeypatch.setattr(GenericFakeChatModel, "_generate", fail)

    with pytest.raises(RuntimeError) as exc_info:
        _invoke(cfg, tmp_path, _fake_model(), model=ref)

    assert len(errors) == expected_calls
    assert exc_info.value is errors[-1]
    (record,) = _read_records(_today_file(tmp_path, "test"))
    assert record.error == f"RuntimeError: attempt {expected_calls}"


def test_invoke_without_retries_calls_model_once(cfg: ModelsConfig, tmp_path: Path) -> None:
    spec = cfg.models["gemini:test-flash"].model_copy(update={"max_retries": 0})
    no_retry = cfg.model_copy(update={"models": {**cfg.models, "gemini:test-flash": spec}})
    model = _FlakyChatModel(messages=iter([]), failures=99)

    with pytest.raises(RuntimeError, match="boom"):
        _invoke(no_retry, tmp_path, model)

    assert model.calls == 1
    (record,) = _read_records(_today_file(tmp_path, "test"))
    assert record.error == "RuntimeError: boom"
