"""Tests for scripts/smoke_providers.py (task 0.6), all offline with fake models."""

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any
from urllib.parse import quote

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

import mia.llm as llm
from mia.llm import ModelsConfig, load_models_config
from mia.schemas import RunRecord

SCRIPT = Path(__file__).parents[1] / "scripts" / "smoke_providers.py"
FIXTURE_MODELS = Path(__file__).parent / "fixtures" / "models.yaml"
REF_A = "gemini:test-flash"
REF_B = "groq:openai/test-oss"


def _load_script() -> ModuleType:
    # scripts/ is not a package, so load the file directly.
    spec = importlib.util.spec_from_file_location("smoke_providers", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # @dataclass looks its module up in sys.modules
    spec.loader.exec_module(module)
    return module


smoke = _load_script()


@pytest.fixture(autouse=True)
def no_retry_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm, "RETRY_WAIT", {"initial": 0, "max": 0, "jitter": 0})


@pytest.fixture
def cfg() -> ModelsConfig:
    return load_models_config(FIXTURE_MODELS)


class _FailingChatModel(GenericFakeChatModel):
    def _generate(self, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("provider down\n" + "x" * 200)


def _ok(text: str, input_tokens: int = 20, output_tokens: int = 10) -> GenericFakeChatModel:
    reply = AIMessage(
        content=text,
        usage_metadata={
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        },
    )
    return GenericFakeChatModel(messages=iter([reply]))


def _failing() -> GenericFakeChatModel:
    return _FailingChatModel(messages=iter([]))


def _records(path: Path) -> list[RunRecord]:
    return [RunRecord.model_validate_json(line) for line in path.read_text("utf-8").splitlines()]


def _use_fakes(
    monkeypatch: pytest.MonkeyPatch,
    cfg: ModelsConfig,
    tmp_path: Path,
    chat_models: dict[str, GenericFakeChatModel],
) -> list[list[str]]:
    """Make main() use the fixture catalog, fake models and tmp_path; return refs it ran."""
    seen: list[list[str]] = []
    real_run_smoke = smoke.run_smoke

    def fake_run_smoke(refs: list[str], **_: Any) -> Any:
        seen.append(list(refs))
        return real_run_smoke(refs, config=cfg, runs_dir=tmp_path, chat_models=chat_models)

    monkeypatch.setattr(smoke, "load_models_config", lambda: cfg)
    monkeypatch.setattr(smoke, "run_smoke", fake_run_smoke)
    return seen


# --- run_smoke (R5, R6) ------------------------------------------------------


def test_run_smoke_records_one_line_per_model_in_order(cfg: ModelsConfig, tmp_path: Path) -> None:
    results, (path,) = smoke.run_smoke(
        [REF_A, REF_B],
        config=cfg,
        runs_dir=tmp_path,
        chat_models={REF_A: _ok("resposta A"), REF_B: _ok("resposta B", 30, 5)},
    )

    assert path == tmp_path / f"{datetime.now(UTC).date().isoformat()}_smoke-providers.jsonl"
    first, second = _records(path)
    assert [first.provider, second.provider] == ["gemini", "groq"]
    assert first.prompt_name == second.prompt_name == "smoke"
    assert first.prompt_version == second.prompt_version == 1
    assert first.experiment == "smoke-providers"
    assert first.params == {"temperature": 0}
    assert first.input_hash == second.input_hash  # same prompt for every model
    assert [r.ok for r in results] == [True, True]
    assert results[1].ref == REF_B
    assert (results[1].input_tokens, results[1].output_tokens) == (30, 5)
    assert results[1].cost_usd == second.cost_usd > 0
    assert results[1].preview == "resposta B"


def test_run_smoke_keeps_going_after_a_failure(cfg: ModelsConfig, tmp_path: Path) -> None:
    results, (path,) = smoke.run_smoke(
        [REF_A, REF_B],
        config=cfg,
        runs_dir=tmp_path,
        chat_models={REF_A: _failing(), REF_B: _ok("ok")},
    )

    failed, passed = _records(path)
    assert failed.error is not None and failed.error.startswith("RuntimeError: provider down")
    assert passed.error is None
    assert [r.ok for r in results] == [False, True]
    assert results[0].preview.startswith("RuntimeError: provider down")


def test_run_smoke_reports_errors_raised_before_any_record(
    cfg: ModelsConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # e.g. a missing provider package: invoke fails while building the model, no RunRecord.
    def broken_init(*args: Any, **kwargs: Any) -> Any:
        raise ImportError("no module named langchain_x")

    monkeypatch.setattr(llm, "init_chat_model", broken_init)

    results, (path,) = smoke.run_smoke(
        [REF_A, REF_B], config=cfg, runs_dir=tmp_path, chat_models={REF_B: _ok("ok")}
    )

    (only,) = _records(path)
    assert only.provider == "groq"
    assert results[0].ok is False
    assert results[0].preview == "ImportError: no module named langchain_x"
    assert (results[0].input_tokens, results[0].cost_usd) == (0, 0.0)
    assert results[1].ok is True


# --- format_table (R7) -------------------------------------------------------


def test_format_table_has_one_row_per_model_with_short_single_line_preview() -> None:
    long_error = "RuntimeError: " + "erro\n" * 50
    results = [
        smoke.SmokeResult(REF_A, True, 20, 10, 812, 0.0000123, "olá"),
        smoke.SmokeResult(REF_B, False, 0, 0, 15, 0.0, long_error),
    ]

    lines = smoke.format_table(results).splitlines()

    row_a = next(line for line in lines if REF_A in line)
    row_b = next(line for line in lines if REF_B in line)
    assert all(part in row_a for part in ("ok", "20", "10", "812", "0.000012", "olá"))
    assert "erro" in row_b
    assert len(lines) == 3
    assert row_b.endswith(" ".join(long_error.split())[:60])
    assert len(row_b[row_b.index("RuntimeError:") :]) == 60


# --- main (R5-R8) ------------------------------------------------------------


def test_main_runs_every_catalog_model_in_file_order(
    cfg: ModelsConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fakes = {ref: _ok("ok") for ref in cfg.models}
    seen = _use_fakes(monkeypatch, cfg, tmp_path, fakes)

    assert smoke.main([]) == 0
    assert seen == [list(cfg.models)]


def test_main_returns_1_when_any_model_fails(
    cfg: ModelsConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use_fakes(monkeypatch, cfg, tmp_path, {REF_A: _failing(), REF_B: _ok("ok")})

    assert smoke.main(["--model", REF_A, "--model", REF_B]) == 1


def test_main_with_model_option_runs_only_those_models(
    cfg: ModelsConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = _use_fakes(monkeypatch, cfg, tmp_path, {REF_B: _ok("ok")})

    assert smoke.main(["--model", REF_B]) == 0
    assert seen == [[REF_B]]


def test_main_rejects_unknown_model_before_calling_anything(
    cfg: ModelsConfig,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    seen = _use_fakes(monkeypatch, cfg, tmp_path, {})

    assert smoke.main(["--model", "groq:nao-existe"]) == 2
    assert seen == []
    assert "groq:nao-existe" in capsys.readouterr().err


def test_main_prints_table_and_jsonl_path_without_secrets(
    cfg: ModelsConfig,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "segredo-teste")
    _use_fakes(monkeypatch, cfg, tmp_path, {REF_B: _ok("resposta do groq")})

    smoke.main(["--model", REF_B])

    captured = capsys.readouterr()
    assert REF_B in captured.out
    assert "resposta do groq" in captured.out
    assert "smoke-providers.jsonl" in captured.out
    assert "segredo-teste" not in captured.out + captured.err


@pytest.mark.parametrize("fails", [False, True])
def test_main_reports_each_record_and_path_across_utc_midnight(
    cfg: ModelsConfig,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    fails: bool,
) -> None:
    class Clock:
        ticks = iter(
            [
                datetime(2026, 11, 15, 23, 59, 59, tzinfo=UTC),
                datetime(2026, 11, 16, 0, 0, 1, tzinfo=UTC),
            ]
        )

        @staticmethod
        def now(tz: Any) -> datetime:
            return next(Clock.ticks)

    monkeypatch.setattr(llm, "datetime", Clock)
    _use_fakes(
        monkeypatch,
        cfg,
        tmp_path,
        {REF_A: _ok("answer A"), REF_B: _failing() if fails else _ok("answer B", 30, 5)},
    )
    assert smoke.main(["--model", REF_A, "--model", REF_B]) == int(fails)
    output = capsys.readouterr().out
    row = next(line for line in output.splitlines() if REF_B in line)
    assert ("provider down" if fails else "answer B") in row
    assert "answer A" not in row
    for day in ("2026-11-15", "2026-11-16"):
        path = tmp_path / f"{day}_smoke-providers.jsonl"
        assert str(path) in output
        assert len(_records(path)) == 1


@pytest.mark.parametrize("during_call", [False, True])
@pytest.mark.parametrize("encoded", [False, True])
@pytest.mark.parametrize("variable", ["GOOGLE_API_KEY", "GROQ_API_KEY", "AWS_SESSION_TOKEN"])
def test_main_redacts_credentials_in_errors_and_records(
    cfg: ModelsConfig,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    during_call: bool,
    encoded: bool,
    variable: str,
) -> None:
    secret = "fictional+credential/value="
    exposed = quote(secret, safe="") if encoded else secret
    monkeypatch.setenv(variable, secret)
    error = RuntimeError(f"invalid key: {exposed}")

    def fail(*args: Any, **kwargs: Any) -> Any:
        raise error

    monkeypatch.setattr(llm, "init_chat_model", fail)
    monkeypatch.setattr(GenericFakeChatModel, "_generate", fail)
    _use_fakes(monkeypatch, cfg, tmp_path, {REF_B: _ok("unused")} if during_call else {})
    assert smoke.main(["--model", REF_B]) == 1
    captured = capsys.readouterr()
    files = list(tmp_path.glob("*.jsonl"))
    persisted = "".join(path.read_text("utf-8") for path in files)
    assert secret not in captured.out + captured.err + persisted
    assert exposed not in captured.out + captured.err + persisted
    assert "invalid key: [REDACTED]" in captured.out
    assert bool(files) == during_call
    if not during_call:
        assert "Nenhum registro gravado." in captured.out
