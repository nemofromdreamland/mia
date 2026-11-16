"""Set B provider and test generator (spec 2.7, step 2). No real model calls."""

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from mia.schemas import ToolMomentItem

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, relative: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


provider = _load("follow_up_provider", "evals/providers/follow_up_provider.py")
tests_set_b = _load("tests_set_b", "evals/tests_set_b.py")


def _items() -> list[ToolMomentItem]:
    path = ROOT / "evals" / "datasets" / "tools.jsonl"
    return [
        ToolMomentItem.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _item(item_id: str = "tool-01") -> ToolMomentItem:
    return next(i for i in _items() if i.item_id == item_id)


def _question(item: ToolMomentItem) -> Any:
    return provider.load_questions()[item.question_id]


def _fake(*replies: str) -> GenericFakeChatModel:
    return GenericFakeChatModel(messages=iter([AIMessage(content=r) for r in replies]))


def _reply(action: str = "follow_up", text: str | None = "Quais métricas?") -> str:
    return json.dumps({"action": action, "follow_up_text": text, "reason": "teste"})


def _records(runs_dir: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for file in sorted(runs_dir.glob("*.jsonl"))
        for line in file.read_text(encoding="utf-8").splitlines()
        if line
    ]


def test_build_state_counts_used_follow_ups() -> None:
    item = _item("tool-24")  # follow_ups_left == 0
    state = provider.build_state(item, _question(item))
    assert item.follow_ups_left == 0
    assert state.follow_ups_used == 2


def test_build_state_partial_use() -> None:
    item = _item("tool-02")  # follow_ups_left == 1
    assert provider.build_state(item, _question(item)).follow_ups_used == 1


def test_history_round_trips_to_the_original_text() -> None:
    from mia.interviewer import _history_text

    for item in _items():
        state = provider.build_state(item, _question(item))
        assert _history_text(state.turns) == item.history


def test_run_tool_item_happy_path(tmp_path: Path) -> None:
    item = _item()
    out = provider.run_tool_item(
        item,
        _question(item),
        model=None,
        experiment="baseline_v1_set_b",
        runs_dir=tmp_path,
        chat_model=_fake(_reply()),
    )
    assert json.loads(out["output"])["action"] == "follow_up"
    meta = out["metadata"]
    assert meta["item_id"] == "tool-01"
    assert meta["split"] == "test"
    assert meta["expected_action"] == "follow_up"
    assert meta["model"]
    records = _records(tmp_path)
    assert len(records) == 1
    assert records[0]["experiment"] == "baseline_v1_set_b"


def test_run_tool_item_returns_error_instead_of_raising(tmp_path: Path) -> None:
    class Boom(GenericFakeChatModel):
        def _generate(self, *args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("x")

    item = _item()
    out = provider.run_tool_item(
        item,
        _question(item),
        model=None,
        experiment="e",
        runs_dir=tmp_path,
        chat_model=Boom(messages=iter([])),
    )
    assert "RuntimeError" in out["error"]


def test_call_api_unknown_question_id_is_an_error() -> None:
    raw = _item().model_dump(mode="json") | {"question_id": "gq-xx"}
    out = provider.call_api("p", {}, {"vars": {"item": raw}})
    assert out["error"].startswith("KeyError")


def test_call_api_reads_config_and_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_run(item: Any, question: Any, *, model: Any, experiment: Any, **kw: Any) -> dict:
        seen.update(model=model, experiment=experiment, item_id=item.item_id)
        return {"output": "{}"}

    monkeypatch.setattr(provider, "run_tool_item", fake_run)
    context = {"vars": {"item": _item().model_dump_json()}}
    provider.call_api("p", {"config": {"model": "bedrock:x", "experiment": "exp"}}, context)
    assert seen == {"model": "bedrock:x", "experiment": "exp", "item_id": "tool-01"}
    provider.call_api("p", {}, context)
    assert seen["model"] is None
    assert seen["experiment"] == provider.DEFAULT_EXPERIMENT == "baseline_v1_set_b"


def test_generate_tests_one_per_item() -> None:
    tests = tests_set_b.generate_tests()
    assert len(tests) == 40
    assert len({t["description"] for t in tests}) == 40
    for test in tests:
        item = ToolMomentItem.model_validate(test["vars"]["item"])
        assert test["vars"]["item_id"] == item.item_id


def test_generate_tests_filters_by_split() -> None:
    tests = tests_set_b.generate_tests({"split": "test"})
    assert len(tests) == 12
    assert {t["vars"]["item"]["split"] for t in tests} == {"test"}
