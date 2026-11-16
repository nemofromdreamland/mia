"""Promptfoo test generator for set A: one test per item of judge_golden.jsonl."""

import os
import sys
from pathlib import Path
from typing import Any, Final


def _ensure_project_python() -> None:
    root = Path(__file__).resolve().parents[1]
    executable = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if executable.exists() and Path(sys.executable).resolve() != executable.resolve():
        os.execv(executable, [str(executable), *sys.argv])


_ensure_project_python()

from mia.schemas import GoldenItem  # noqa: E402 - interpreter guard must run first

GOLDEN_PATH: Final = Path(__file__).resolve().parent / "datasets" / "judge_golden.jsonl"


def _load_items(path: Path = GOLDEN_PATH) -> list[GoldenItem]:
    return [
        GoldenItem.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def item_to_test(item: GoldenItem) -> dict[str, Any]:
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
    return [item_to_test(item) for item in items]
