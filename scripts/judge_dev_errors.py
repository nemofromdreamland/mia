"""Task 2.9: list the judge's errors on the dev split, from an existing export.

Usage:
    uv run python scripts/judge_dev_errors.py results/baseline_v1_set_a.json --label <provider>

Read-only, no model calls. Test-split items are never printed: the test split is not
used to tune prompts (TRD "Regras do golden set"). Exit codes: 0 ok, 1 unreadable
export, 2 `--split test` requested.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCALE: tuple[int, ...] = (1, 2, 3, 4, 5)


@dataclass(frozen=True)
class DevError:
    item_id: str
    variant: str
    human_score: int
    judge_score: int | None  # None = provider error or output outside the schema
    justification: str
    dropped_quotes: int  # 1 when the judge had unverifiable quotes dropped (count is not kept)


def _parse_output(result: dict[str, Any]) -> dict[str, Any] | None:
    response = result.get("response") or {}
    if response.get("error"):
        return None
    try:
        data = json.loads(response.get("output") or "")
    except (json.JSONDecodeError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def _to_error(result: dict[str, Any]) -> DevError | None:
    item = (result.get("testCase") or {}).get("vars", {}).get("item") or {}
    if isinstance(item, str):
        item = json.loads(item)
    if item.get("split") != "dev" or not isinstance(item.get("human_score"), int):
        return None
    data = _parse_output(result)
    score = data.get("score") if data else None
    valid = isinstance(score, int) and not isinstance(score, bool) and score in SCALE
    return DevError(
        item_id=item["item_id"],
        variant=item.get("variant", ""),
        human_score=item["human_score"],
        judge_score=score if valid else None,
        justification=str(data.get("justification", "")) if data else "",
        dropped_quotes=1 if data and data.get("quotes_verified") is False else 0,
    )


def dev_errors(export_path: Path, label: str | None = None, min_gap: int = 1) -> list[DevError]:
    """Dev items where |judge - human| >= min_gap, or the judge failed. Never test items."""
    raw = json.loads(export_path.read_text(encoding="utf-8"))
    errors: list[DevError] = []
    for result in raw["results"]["results"]:
        if label is not None and (result.get("provider") or {}).get("label") != label:
            continue
        error = _to_error(result)
        if error is None:
            continue
        if error.judge_score is None or abs(error.judge_score - error.human_score) >= min_gap:
            errors.append(error)
    return errors


def render_errors(errors: Sequence[DevError]) -> str:
    if not errors:
        return "Nenhum erro no dev.\n"
    lines = [f"{len(errors)} erro(s) no dev (humano -> juiz):", ""]
    for e in errors:
        judge = "erro" if e.judge_score is None else str(e.judge_score)
        dropped = " [citação descartada]" if e.dropped_quotes else ""
        lines.append(f"- {e.item_id} ({e.variant}): {e.human_score} -> {judge}{dropped}")
        if e.justification:
            lines.append(f"    {e.justification}")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="List judge errors on the dev split.")
    parser.add_argument("export", type=Path, help="Promptfoo export JSON of set A")
    parser.add_argument("--label", help="provider label to keep (default: all)")
    parser.add_argument("--min-gap", type=int, default=1)
    parser.add_argument("--split", default="dev")
    args = parser.parse_args(argv)
    if args.split != "dev":
        print("O split de teste não é usado para ajuste: só 'dev' é permitido.", file=sys.stderr)
        return 2
    try:
        errors = dev_errors(args.export, args.label, args.min_gap)
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"{args.export}: export ilegível ({exc})", file=sys.stderr)
        return 1
    print(render_errors(errors), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
