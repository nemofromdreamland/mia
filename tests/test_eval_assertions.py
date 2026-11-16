"""Tests for the Promptfoo Python assertions of set A (task 2.5, step 1)."""

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ASSERTS_PATH = Path(__file__).resolve().parents[1] / "evals" / "assertions" / "judge_asserts.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("judge_asserts", ASSERTS_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ja = _load_module()


def _output(**overrides: Any) -> str:
    data: dict[str, Any] = {
        "score": 4,
        "criteria_met": ["a"],
        "evidence_quotes": ["x"],
        "justification": "ok",
        "quotes_verified": True,
    }
    data.update(overrides)
    return json.dumps(data)


def _context(human_score: int | None = 3) -> dict[str, Any]:
    return {"vars": {"item": {"item_id": "gq-tech-01-level_3", "human_score": human_score}}}


def test_schema_passes_on_valid_answer_score() -> None:
    result = ja.assert_schema(_output(), _context())
    assert result["pass"] is True
    assert result["score"] == 1.0


@pytest.mark.parametrize("output", ["oi", _output(score=9), json.dumps({"score": 3})])
def test_schema_fails_on_invalid_output(output: str) -> None:
    result = ja.assert_schema(output, _context())
    assert result["pass"] is False
    assert result["score"] == 0.0
    assert result["reason"]


def test_quotes_verified_true_passes() -> None:
    assert ja.assert_quotes_verified(_output(), _context())["pass"] is True


def test_quotes_verified_false_fails() -> None:
    result = ja.assert_quotes_verified(_output(quotes_verified=False), _context())
    assert result["pass"] is False
    assert "citação" in result["reason"]


def test_score_within_one_passes_with_partial_score() -> None:
    result = ja.assert_score_within_one(_output(score=4), _context(3))
    assert result["pass"] is True
    assert result["score"] == pytest.approx(0.75)
    assert "4" in result["reason"] and "3" in result["reason"]


def test_score_off_by_two_fails() -> None:
    result = ja.assert_score_within_one(_output(score=5), _context(3))
    assert result["pass"] is False
    assert result["score"] == pytest.approx(0.5)


def test_score_accepts_item_as_json_string() -> None:
    context = {"vars": {"item": json.dumps({"human_score": 4})}}
    assert ja.assert_score_within_one(_output(score=4), context)["score"] == 1.0


def test_score_fails_without_human_score() -> None:
    result = ja.assert_score_within_one(_output(), _context(None))
    assert result["pass"] is False
    assert "human_score" in result["reason"]


@pytest.mark.parametrize(
    "check", ["assert_schema", "assert_quotes_verified", "assert_score_within_one"]
)
def test_provider_error_output_fails_all(check: str) -> None:
    output = json.dumps({"error": "LLMInvalidOutputError: bad json"})
    result = getattr(ja, check)(output, _context())
    assert result["pass"] is False
    assert "LLMInvalidOutputError" in result["reason"]
