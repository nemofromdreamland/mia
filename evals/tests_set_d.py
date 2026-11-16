"""Promptfoo test generator for set D: one test per item of robustness.jsonl.

Items are interleaved by attack type (one of each type, then the next round), so
``--filter-first-n 5`` is a smoke run with one item per type.
"""

import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Final


def _ensure_project_python() -> None:
    root = Path(__file__).resolve().parents[1]
    executable = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if executable.exists() and Path(sys.executable).resolve() != executable.resolve():
        os.execv(executable, [str(executable), *sys.argv])


_ensure_project_python()

from mia.schemas import RobustnessItem  # noqa: E402 - interpreter guard must run first

ROBUSTNESS_PATH: Final = Path(__file__).resolve().parent / "datasets" / "robustness.jsonl"


def _load_items(path: Path = ROBUSTNESS_PATH) -> list[RobustnessItem]:
    return [
        RobustnessItem.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _interleave(items: list[RobustnessItem]) -> list[RobustnessItem]:
    groups: dict[str, list[RobustnessItem]] = defaultdict(list)
    for item in items:
        groups[item.attack_type].append(item)
    rounds = max(len(group) for group in groups.values())
    return [group[i] for i in range(rounds) for group in groups.values() if i < len(group)]


def item_to_test(item: RobustnessItem) -> dict[str, Any]:
    return {
        "description": item.item_id,
        "vars": {"item_id": item.item_id, "item": item.model_dump(mode="json")},
    }


def generate_tests(config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Tests for all items, or only one split when config has split = dev | test."""
    split = (config or {}).get("split")
    items = _load_items()
    if split in ("dev", "test"):
        items = [item for item in items if item.split == split]
    return [item_to_test(item) for item in _interleave(items)]
