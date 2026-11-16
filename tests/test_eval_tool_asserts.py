"""Tests for the Promptfoo Python assertions of set B (task 2.7, step 1)."""

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from mia.schemas import ToolDecision

ASSERTS_PATH = Path(__file__).resolve().parents[1] / "evals" / "assertions" / "tool_asserts.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("tool_asserts", ASSERTS_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ta = _load_module()

MUST_ADDRESS = [
    "Propõe um conjunto de casos de teste fixo, usado nas duas versões",
    "Define critérios ou métricas de qualidade antes de comparar",
]


def _output(action: str = "follow_up", text: str | None = "Como você testaria?") -> str:
    return json.dumps({"action": action, "follow_up_text": text, "reason": "r"})


def _context(
    expected: str = "follow_up",
    follow_ups_left: int = 2,
    must_address: list[str] | None = None,
    as_string: bool = False,
) -> dict[str, Any]:
    item = {
        "item_id": "tool-01",
        "follow_ups_left": follow_ups_left,
        "expected": {
            "action": expected,
            "follow_up_must_address": must_address if must_address is not None else [],
        },
    }
    return {"vars": {"item": json.dumps(item) if as_string else item}}


# effective_action


def test_effective_action_keeps_follow_up_with_text_and_slot() -> None:
    decision = ToolDecision(action="follow_up", follow_up_text="Por quê?", reason="r")
    assert ta.effective_action(decision, follow_ups_left=1) == "follow_up"


def test_effective_action_without_slot_becomes_next_question() -> None:
    decision = ToolDecision(action="follow_up", follow_up_text="Por quê?", reason="r")
    assert ta.effective_action(decision, follow_ups_left=0) == "next_question"


@pytest.mark.parametrize("text", [None, "", "   "])
def test_effective_action_without_text_becomes_next_question(text: str | None) -> None:
    decision = ToolDecision(action="follow_up", follow_up_text=text, reason="r")
    assert ta.effective_action(decision, follow_ups_left=2) == "next_question"


@pytest.mark.parametrize("action", ["next_question", "end"])
def test_effective_action_keeps_other_actions(action: str) -> None:
    decision = ToolDecision(action=action, reason="r")  # type: ignore[arg-type]
    assert ta.effective_action(decision, follow_ups_left=0) == action


# schema


def test_schema_passes_on_valid_decision() -> None:
    assert ta.assert_tool_schema(_output(), _context())["pass"] is True


@pytest.mark.parametrize(
    ("output", "reason_part"),
    [
        ("oops", "não é JSON"),
        (json.dumps({"error": "RuntimeError: x"}), "erro do provider"),
        (json.dumps({"action": "dance", "reason": "r"}), "ToolDecision"),
    ],
)
def test_all_asserts_fail_on_bad_output(output: str, reason_part: str) -> None:
    for fn in (ta.assert_tool_schema, ta.assert_tool_action, ta.assert_tool_args):
        result = fn(output, _context())
        assert result["pass"] is False
        assert result["score"] == 0.0
        assert reason_part in result["reason"]


# action


def test_action_passes_when_equal() -> None:
    result = ta.assert_tool_action(_output("end", None), _context("end"))
    assert result == {"pass": True, "score": 1.0, "reason": "esperado end, obtido end"}


def test_action_follow_up_without_slot_counts_as_next_question() -> None:
    result = ta.assert_tool_action(_output("follow_up"), _context("next_question", 0))
    assert result["pass"] is True


def test_action_follow_up_without_text_fails_when_follow_up_expected() -> None:
    result = ta.assert_tool_action(_output("follow_up", ""), _context("follow_up"))
    assert result["pass"] is False
    assert "obtido next_question" in result["reason"]


def test_action_reads_item_as_json_string() -> None:
    result = ta.assert_tool_action(_output("end", None), _context("end", as_string=True))
    assert result["pass"] is True


# args


def test_args_not_applicable_when_not_follow_up_expected() -> None:
    result = ta.assert_tool_args(_output("next_question", None), _context("next_question"))
    assert result == {"pass": True, "score": 1.0, "reason": "não se aplica"}


def test_args_not_applicable_when_action_wrong() -> None:
    result = ta.assert_tool_args(_output("end", None), _context("follow_up", 2, MUST_ADDRESS))
    assert result["pass"] is True
    assert result["reason"] == "não se aplica"


def test_args_pass_when_text_covers_every_item() -> None:
    text = "Que casos de teste você usaria, e com quais métricas compararia as versões?"
    result = ta.assert_tool_args(_output(text=text), _context("follow_up", 2, MUST_ADDRESS))
    assert result["pass"] is True
    assert result["score"] == 1.0


def test_args_fail_when_one_item_missing() -> None:
    text = "Que casos de teste você usaria?"
    result = ta.assert_tool_args(_output(text=text), _context("follow_up", 2, MUST_ADDRESS))
    assert result["pass"] is False
    assert result["score"] == 0.5
    assert "Define critérios" in result["reason"]


def test_args_match_ignores_accents_case_and_inflection() -> None:
    must = ["Explica a métrica de latência"]
    text = "E as METRICAS de latencia, como mediria?"
    result = ta.assert_tool_args(_output(text=text), _context("follow_up", 2, must))
    assert result["pass"] is True


def test_args_stopwords_alone_do_not_match() -> None:
    must = ["Explica para quem usaria isso"]
    text = "Para quem você faria isso?"  # shares only stopwords with the item
    result = ta.assert_tool_args(_output(text=text), _context("follow_up", 2, must))
    assert result["pass"] is False


def test_keywords_drop_stopwords_and_short_words() -> None:
    assert ta.keywords("Define critérios de qualidade antes de comparar") == [
        "define",
        "criterios",
        "qualidade",
        "antes",
        "comparar",
    ]
