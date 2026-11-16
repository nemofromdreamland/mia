"""Tests for the Promptfoo provider and test generator of set A (task 2.5, step 2)."""

import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from mia.schemas import GoldenItem

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, relative: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


provider = _load("judge_provider", "evals/providers/judge_provider.py")
tests_set_a = _load("tests_set_a", "evals/tests_set_a.py")


def _items() -> list[GoldenItem]:
    path = ROOT / "evals" / "datasets" / "judge_golden.jsonl"
    return [
        GoldenItem.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _item() -> GoldenItem:
    return next(i for i in _items() if i.item_id == "gq-tech-01-level_5")


def _fake(*replies: str) -> GenericFakeChatModel:
    return GenericFakeChatModel(messages=iter([AIMessage(content=r) for r in replies]))


def _reply(quotes: list[str]) -> str:
    item = _item()
    return json.dumps(
        {
            "score": 4,
            "criteria_met": [item.question.look_for[0]],
            "evidence_quotes": quotes,
            "justification": "Resposta com exemplo.",
        },
        ensure_ascii=False,
    )


def _records(runs_dir: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for file in sorted(runs_dir.glob("*.jsonl"))
        for line in file.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _real_quote() -> str:
    return " ".join(_item().answer_text.split()[:4])


def test_run_item_happy_path(tmp_path: Path) -> None:
    item = _item()
    result = provider.run_item(
        item,
        model=None,
        experiment="promptfoo_set_a",
        runs_dir=tmp_path,
        chat_model=_fake(_reply([_real_quote()])),
    )
    output = json.loads(result["output"])
    assert output["score"] == 4
    assert output["quotes_verified"] is True
    meta = result["metadata"]
    assert meta["item_id"] == item.item_id
    assert meta["variant"] == item.variant
    assert meta["split"] == item.split
    assert meta["human_score"] == item.human_score
    assert meta["model"]


def test_run_item_drops_invented_quote(tmp_path: Path) -> None:
    reply = _reply([_real_quote(), "frase que a pessoa nunca disse"])
    result = provider.run_item(
        _item(), model=None, experiment="x", runs_dir=tmp_path, chat_model=_fake(reply)
    )
    output = json.loads(result["output"])
    assert output["quotes_verified"] is False
    assert "frase que a pessoa nunca disse" not in output["evidence_quotes"]


def test_run_item_passes_model_to_run_record(tmp_path: Path) -> None:
    result = provider.run_item(
        _item(),
        model="bedrock:us.amazon.nova-2-lite-v1:0",
        experiment="x",
        runs_dir=tmp_path,
        chat_model=_fake(_reply([])),
    )
    assert result["metadata"]["model"] == "bedrock:us.amazon.nova-2-lite-v1:0"
    assert _records(tmp_path)[0]["model"] == "us.amazon.nova-2-lite-v1:0"


def test_run_item_records_default_experiment(tmp_path: Path) -> None:
    provider.run_item(
        _item(),
        model=None,
        experiment=provider.DEFAULT_EXPERIMENT,
        runs_dir=tmp_path,
        chat_model=_fake(_reply([])),
    )
    assert [r["experiment"] for r in _records(tmp_path)] == ["promptfoo_set_a"]
    assert provider.DEFAULT_EXPERIMENT == "promptfoo_set_a"


def test_run_item_returns_error_instead_of_raising(tmp_path: Path) -> None:
    result = provider.run_item(
        _item(),
        model=None,
        experiment="x",
        runs_dir=tmp_path,
        chat_model=_fake("lixo", "lixo"),
    )
    assert result["error"].startswith("LLMInvalidOutputError:")


def test_call_api_reads_config_and_vars(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_run_item(item: GoldenItem, **kwargs: Any) -> dict[str, Any]:
        seen.update(item_id=item.item_id, **kwargs)
        return {"output": "{}"}

    monkeypatch.setattr(provider, "run_item", fake_run_item)
    item = _item()
    context = {"vars": {"item": item.model_dump(mode="json")}}
    options = {"config": {"model": "bedrock:m", "experiment": "exp_y"}}
    assert provider.call_api("{{item_id}}", options, context) == {"output": "{}"}
    assert seen == {"item_id": item.item_id, "model": "bedrock:m", "experiment": "exp_y"}


def test_call_api_defaults_and_string_item(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}
    monkeypatch.setattr(
        provider, "run_item", lambda item, **kw: seen.update(kw) or {"output": "{}"}
    )
    context = {"vars": {"item": _item().model_dump_json()}}
    provider.call_api("p", {}, context)
    assert seen == {"model": None, "experiment": "promptfoo_set_a"}


def test_generate_tests_one_per_item() -> None:
    tests = tests_set_a.generate_tests()
    assert len(tests) == 70
    assert len({t["description"] for t in tests}) == 70
    for test in tests:
        item = GoldenItem.model_validate(test["vars"]["item"])
        assert test["description"] == item.item_id
        assert test["vars"]["item_id"] == item.item_id


def test_generate_tests_filters_by_split() -> None:
    tests = tests_set_a.generate_tests({"split": "test"})
    assert len(tests) == 21
    assert {t["vars"]["item"]["split"] for t in tests} == {"test"}
    assert len(tests_set_a.generate_tests({"split": "all"})) == 70


def test_promptfoo_python_can_load_eval_modules() -> None:
    venv_dir = (ROOT / ".venv").resolve()
    external_path = os.pathsep.join(
        entry
        for entry in os.environ["PATH"].split(os.pathsep)
        if venv_dir not in Path(entry).resolve().parents and Path(entry).resolve() != venv_dir
    )
    python = shutil.which("python", path=external_path)
    assert python is not None
    code = (
        "import runpy; "
        "runpy.run_path('evals/tests_set_a.py'); "
        "runpy.run_path('evals/assertions/judge_asserts.py')"
    )
    result = subprocess.run(
        [python, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
