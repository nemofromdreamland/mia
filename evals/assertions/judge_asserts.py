"""Promptfoo Python assertions for set A (judge).

Promptfoo calls each function with the provider output (a JSON string) and a context
whose ``vars["item"]`` is the GoldenItem of the test. Each returns a GradingResult dict:
{"pass": bool, "score": float, "reason": str}.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any


def _ensure_project_python() -> None:
    root = Path(__file__).resolve().parents[2]
    executable = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if executable.exists() and Path(sys.executable).resolve() != executable.resolve():
        os.execv(executable, [str(executable), *sys.argv])


_ensure_project_python()

from pydantic import ValidationError  # noqa: E402 - interpreter guard must run first

from mia.schemas import AnswerScore  # noqa: E402 - interpreter guard must run first

GradingResult = dict[str, Any]


def _result(passed: bool, score: float, reason: str) -> GradingResult:
    return {"pass": passed, "score": score, "reason": reason}


def _parse(output: str) -> AnswerScore | GradingResult:
    """AnswerScore, or a failing result when the output is a provider error or invalid."""
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return _result(False, 0.0, "saída não é JSON")
    if isinstance(data, dict) and "error" in data:
        return _result(False, 0.0, f"erro do provider: {data['error']}")
    try:
        return AnswerScore.model_validate(data)
    except ValidationError as exc:
        return _result(False, 0.0, f"não valida como AnswerScore: {exc.error_count()} erro(s)")


def _human_score(context: dict[str, Any]) -> int | None:
    item = context.get("vars", {}).get("item", {})
    if isinstance(item, str):
        item = json.loads(item)
    return item.get("human_score")


def assert_schema(output: str, context: dict[str, Any]) -> GradingResult:
    parsed = _parse(output)
    if isinstance(parsed, dict):
        return parsed
    return _result(True, 1.0, "AnswerScore válido")


def assert_quotes_verified(output: str, context: dict[str, Any]) -> GradingResult:
    parsed = _parse(output)
    if isinstance(parsed, dict):
        return parsed
    if parsed.quotes_verified:
        return _result(True, 1.0, "toda citação é literal na resposta")
    return _result(False, 0.0, "alguma citação não está literal na resposta")


def assert_score_within_one(output: str, context: dict[str, Any]) -> GradingResult:
    parsed = _parse(output)
    if isinstance(parsed, dict):
        return parsed
    human = _human_score(context)
    if human is None:
        return _result(False, 0.0, "item sem human_score")
    diff = abs(parsed.score - human)
    reason = f"juiz {parsed.score} vs humano {human}"
    return _result(diff <= 1, 1 - diff / 4, reason)
