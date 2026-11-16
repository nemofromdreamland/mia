"""Promptfoo Python assertions for set B (follow_up tool decisions).

Promptfoo calls each function with the provider output (a ToolDecision as JSON) and a context
whose ``vars["item"]`` is the ToolMomentItem of the test. Each returns a GradingResult dict:
{"pass": bool, "score": float, "reason": str}.

The argument check is deterministic (spec 2.7, P1): each ``follow_up_must_address`` entry must
share at least one keyword with ``follow_up_text``. Keywords are lowercased, accent-free words of
4+ letters that are not stopwords, compared by their first 5 letters so simple inflections
("métrica" / "métricas") match. Synonyms do not match: that limit is reported with the results.
"""

import json
import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any


def _ensure_project_python() -> None:
    root = Path(__file__).resolve().parents[2]
    executable = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if executable.exists() and Path(sys.executable).resolve() != executable.resolve():
        os.execv(executable, [str(executable), *sys.argv])


_ensure_project_python()

from pydantic import ValidationError  # noqa: E402 - interpreter guard must run first

from mia.schemas import ToolDecision  # noqa: E402 - interpreter guard must run first

GradingResult = dict[str, Any]

MIN_WORD_LEN = 4
STEM_LEN = 5
STOPWORDS = frozenset(
    {
        "para", "quem", "isso", "isto", "aquilo", "como", "voce", "mais", "menos", "esse",
        "essa", "este", "esta", "pelo", "pela", "pelos", "pelas", "sobre", "entre", "cada",
        "qual", "quais", "quando", "onde", "porque", "seus", "suas", "seu", "sua", "deve",
        "umas", "outro", "outra", "muito", "muita", "tambem", "ainda", "mesmo", "mesma",
        "with", "that", "this", "from", "what", "which", "when", "where", "your", "about",
    }
)  # fmt: skip
_WORD = re.compile(r"[a-z0-9]+")


def _result(passed: bool, score: float, reason: str) -> GradingResult:
    return {"pass": passed, "score": score, "reason": reason}


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def keywords(text: str) -> list[str]:
    """Content words of `text`: normalized, 4+ letters, no stopwords, in order."""
    words = _WORD.findall(_normalize(text))
    return [w for w in words if len(w) >= MIN_WORD_LEN and w not in STOPWORDS]


def _stems(text: str) -> set[str]:
    return {w[:STEM_LEN] for w in keywords(text)}


def effective_action(decision: ToolDecision, follow_ups_left: int) -> str:
    """Action the product would take: mirrors interviewer._wants_follow_up (the code decides)."""
    if decision.action != "follow_up":
        return decision.action
    has_text = bool(decision.follow_up_text and decision.follow_up_text.strip())
    return "follow_up" if has_text and follow_ups_left > 0 else "next_question"


def _parse(output: str) -> ToolDecision | GradingResult:
    """ToolDecision, or a failing result when the output is a provider error or invalid."""
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return _result(False, 0.0, "saída não é JSON")
    if isinstance(data, dict) and "error" in data:
        return _result(False, 0.0, f"erro do provider: {data['error']}")
    try:
        return ToolDecision.model_validate(data)
    except ValidationError as exc:
        return _result(False, 0.0, f"não valida como ToolDecision: {exc.error_count()} erro(s)")


def _item(context: dict[str, Any]) -> dict[str, Any]:
    item = context.get("vars", {}).get("item", {})
    return json.loads(item) if isinstance(item, str) else item


def assert_tool_schema(output: str, context: dict[str, Any]) -> GradingResult:
    parsed = _parse(output)
    if isinstance(parsed, dict):
        return parsed
    return _result(True, 1.0, "ToolDecision válido")


def assert_tool_action(output: str, context: dict[str, Any]) -> GradingResult:
    parsed = _parse(output)
    if isinstance(parsed, dict):
        return parsed
    item = _item(context)
    expected = item["expected"]["action"]
    got = effective_action(parsed, item["follow_ups_left"])
    return _result(got == expected, float(got == expected), f"esperado {expected}, obtido {got}")


def assert_tool_args(output: str, context: dict[str, Any]) -> GradingResult:
    parsed = _parse(output)
    if isinstance(parsed, dict):
        return parsed
    item = _item(context)
    must_address: list[str] = item["expected"].get("follow_up_must_address", [])
    got = effective_action(parsed, item["follow_ups_left"])
    if item["expected"]["action"] != "follow_up" or got != "follow_up" or not must_address:
        return _result(True, 1.0, "não se aplica")
    text_stems = _stems(parsed.follow_up_text or "")
    missing = [m for m in must_address if not _stems(m) & text_stems]
    covered = len(must_address) - len(missing)
    score = covered / len(must_address)
    if missing:
        return _result(False, score, "não cobre: " + "; ".join(missing))
    return _result(True, score, f"cobre os {len(must_address)} itens")
