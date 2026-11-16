"""Task 2.3: read and write the golden set A JSONL, validated and atomic."""

import os
from pathlib import Path
from typing import Final

from mia.schemas import GoldenItem

GOLDEN_PATH: Final[Path] = (
    Path(__file__).resolve().parent.parent / "evals" / "datasets" / "judge_golden.jsonl"
)


def load_items(path: Path = GOLDEN_PATH) -> list[GoldenItem]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [GoldenItem.model_validate_json(line) for line in lines if line.strip()]


def save_items(items: list[GoldenItem], path: Path = GOLDEN_PATH) -> None:
    """Validate every item, write to a temp file, then replace: a crash never corrupts the file."""
    validated = [GoldenItem.model_validate(item.model_dump()) for item in items]
    content = "".join(item.model_dump_json() + "\n" for item in validated)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)
