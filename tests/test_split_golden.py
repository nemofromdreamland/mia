"""Tests for scripts/split_golden.py (task 2.3, step 2)."""

import importlib.util
import sys
from collections import Counter
from pathlib import Path
from types import ModuleType

import pytest

from mia.schemas import GoldenItem, Question

SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gio = _load("golden_io")
sg = _load("split_golden")

VARIANTS = ["level_5", "level_4", "level_3", "level_2", "level_1", "rambling", "paraphrase"]


def _make(q: int, variant: str, score: int | None = 3) -> GoldenItem:
    question = Question(
        id=f"gq-{q:02d}",
        phase="technical",
        competency="Avaliação",
        text=f"Pergunta {q}?",
        purpose="Ver se avalia.",
        look_for=["A", "B", "C"],
        follow_ups=[],
        targets_concern=None,
    )
    return GoldenItem(
        item_id=f"gq-{q:02d}-{variant}",
        question=question,
        answer_text=f"Resposta {q} {variant}.",
        variant=variant,
        paraphrase_of=f"gq-{q:02d}-level_3" if variant == "paraphrase" else None,
        human_score=score,
        generated_by="groq:x|synthetic_candidate@v4",
    )


def _full(score: int | None = 3) -> list[GoldenItem]:
    return [_make(q, v, score) for q in range(1, 11) for v in VARIANTS]


def test_assign_splits_counts_and_pairing() -> None:
    result = sg.assign_splits(_full())
    assert Counter(i.split for i in result) == {"dev": 49, "test": 21}
    for variant in VARIANTS:
        counts = Counter(i.split for i in result if i.variant == variant)
        assert counts == {"dev": 7, "test": 3}
    by_id = {i.item_id: i for i in result}
    for item in result:
        if item.paraphrase_of:
            assert item.split == by_id[item.paraphrase_of].split


def test_assign_splits_is_deterministic() -> None:
    assert sg.assign_splits(_full()) == sg.assign_splits(_full())


def test_main_happy_path_writes_file(tmp_path: Path) -> None:
    path = tmp_path / "g.jsonl"
    gio.save_items(_full(), path)
    assert sg.main([], path=path) == 0
    assert Counter(i.split for i in gio.load_items(path)) == {"dev": 49, "test": 21}


def test_main_refuses_when_scores_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "g.jsonl"
    items = _full()
    items[0] = _make(1, "level_5", score=None)
    gio.save_items(items, path)
    before = path.read_text(encoding="utf-8")
    assert sg.main([], path=path) == 1
    assert "falta 1" in capsys.readouterr().out
    assert path.read_text(encoding="utf-8") == before


def test_main_refuses_existing_split_without_force(tmp_path: Path) -> None:
    path = tmp_path / "g.jsonl"
    gio.save_items(sg.assign_splits(_full()), path)
    before = path.read_text(encoding="utf-8")
    assert sg.main([], path=path) == 1
    assert path.read_text(encoding="utf-8") == before
    assert sg.main(["--force"], path=path) == 0
