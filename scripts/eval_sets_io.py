"""Task 2.4: read/write the eval set JSONLs (B, C, D), validated and atomic, and split them."""

import os
import random
from collections import defaultdict
from collections.abc import Callable, Sequence
from pathlib import Path

from pydantic import BaseModel, ValidationError


def load_jsonl[T: BaseModel](path: Path, model: type[T]) -> list[T]:
    """Validate each non-blank line; errors name the line number."""
    items: list[T] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            items.append(model.model_validate_json(line))
        except ValidationError as exc:
            raise ValueError(f"{path.name} line {number}: {exc}") from exc
    return items


def save_jsonl(items: Sequence[BaseModel], path: Path) -> None:
    """Revalidate every item, write to a temp file, then replace (a crash never corrupts it)."""
    validated = [type(item).model_validate(item.model_dump()) for item in items]
    content = "".join(item.model_dump_json() + "\n" for item in validated)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def assign_splits[T: BaseModel](
    items: list[T], stratum: Callable[[T], str], seed: int, dev_ratio: float = 0.7
) -> list[T]:
    """Return copies with `split` set: round(dev_ratio * n) per stratum go to dev (seeded)."""
    groups: dict[str, list[str]] = defaultdict(list)
    for item in items:
        groups[stratum(item)].append(item.item_id)  # type: ignore[attr-defined]
    rng = random.Random(seed)
    dev: set[str] = set()
    for key in sorted(groups):
        ids = sorted(groups[key])
        rng.shuffle(ids)
        dev.update(ids[: round(dev_ratio * len(ids))])
    return [
        item.model_copy(update={"split": "dev" if item.item_id in dev else "test"})  # type: ignore[attr-defined]
        for item in items
    ]
