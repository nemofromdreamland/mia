"""Task 2.3: blind human labeling of the golden set A, one answer at a time.

Usage:
    uv run python scripts/label_golden.py

Shows only the question, its look_for criteria and the answer (never the variant).
Type 1-5 to score, q to quit. Each score is saved immediately; rerun to resume.
"""

import argparse
import random
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Final, Literal

from golden_io import GOLDEN_PATH, load_items, save_items

from mia.schemas import GoldenItem

SHUFFLE_SEED: Final = 2303
INVALID_MSG: Final = "Entrada inválida: digite um número de 1 a 5, ou q para sair."
NOTHING_MSG: Final = "Nada a rotular: todos os itens já têm nota."
PROMPT: Final = "Nota (1-5, q para sair): "


def presentation_order(items: list[GoldenItem], seed: int = SHUFFLE_SEED) -> list[int]:
    """Indices of unscored items, shuffled with a fixed seed so levels don't come in sequence."""
    order = list(range(len(items)))
    random.Random(seed).shuffle(order)
    return [i for i in order if items[i].human_score is None]


def render_item(item: GoldenItem, position: int, total: int) -> str:
    criteria = "\n".join(f"  - {c}" for c in item.question.look_for)
    return (
        f"\n===== Item {position} de {total} =====\n"
        f"PERGUNTA:\n{item.question.text}\n\n"
        f"O QUE PROCURAR:\n{criteria}\n\n"
        f"RESPOSTA:\n{item.answer_text}\n"
    )


def parse_score(raw: str) -> int | Literal["quit"] | None:
    value = raw.strip().lower()
    if value == "q":
        return "quit"
    if value in {"1", "2", "3", "4", "5"}:
        return int(value)
    return None


def _ask(input_fn: Callable[[str], str]) -> int | Literal["quit"]:
    while (score := parse_score(input_fn(PROMPT))) is None:
        print(INVALID_MSG)
    return score


def main(
    argv: Sequence[str] | None = None,
    *,
    input_fn: Callable[[str], str] = input,
    path: Path = GOLDEN_PATH,
) -> int:
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    items = load_items(path)
    order = presentation_order(items)
    if not order:
        print(NOTHING_MSG)
        return 0
    for position, index in enumerate(order, start=1):
        print(render_item(items[index], position, len(order)))
        score = _ask(input_fn)
        if score == "quit":
            print(f"Saindo. Faltam {len(order) - position + 1} itens.")
            return 0
        items[index] = items[index].model_copy(update={"human_score": score})
        save_items(items, path)
    print("Pronto: todos os itens têm nota.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
