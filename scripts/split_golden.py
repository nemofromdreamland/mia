"""Task 2.3: split golden set A into dev (70%) and test (30%), stratified by variant."""

import argparse
import random
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from golden_io import GOLDEN_PATH, load_items, save_items

from mia.schemas import GoldenItem

SPLIT_SEED: Final[int] = 2304
DEV_PER_VARIANT: Final[int] = 7


def assign_splits(items: list[GoldenItem], seed: int = SPLIT_SEED) -> list[GoldenItem]:
    """Per variant: 7 items to dev, the rest to test. A paraphrase copies its original's split."""
    rng = random.Random(seed)
    chosen: dict[str, str] = {}
    variants = sorted({i.variant for i in items if i.paraphrase_of is None})
    for variant in variants:
        ids = sorted(i.item_id for i in items if i.variant == variant)
        rng.shuffle(ids)
        for position, item_id in enumerate(ids):
            chosen[item_id] = "dev" if position < DEV_PER_VARIANT else "test"
    for item in items:
        if item.paraphrase_of is not None:
            chosen[item.item_id] = chosen[item.paraphrase_of]
    return [item.model_copy(update={"split": chosen[item.item_id]}) for item in items]


def main(argv: Sequence[str] | None = None, *, path: Path = GOLDEN_PATH) -> int:
    parser = argparse.ArgumentParser(description="Split the golden set into dev/test.")
    parser.add_argument("--force", action="store_true", help="redo an existing split")
    args = parser.parse_args(argv)

    items = load_items(path)
    missing = sum(1 for i in items if i.human_score is None)
    if missing:
        print(f"Não dá para dividir: falta {missing} nota(s) humana(s).")
        return 1
    if any(i.split is not None for i in items) and not args.force:
        print("O split já existe. Use --force para refazer.")
        return 1
    save_items(assign_splits(items), path)
    print(f"Split gravado em {path.name}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
