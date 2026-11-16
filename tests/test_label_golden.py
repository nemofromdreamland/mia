"""Tests for scripts/golden_io.py and scripts/label_golden.py (task 2.3, step 1)."""

import importlib.util
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from types import ModuleType

import pytest
from pydantic import ValidationError

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
lg = _load("label_golden")


def _item(n: int, variant: str = "level_5", score: int | None = None) -> GoldenItem:
    question = Question(
        id=f"gq-tech-0{n}",
        phase="technical",
        competency="Avaliação",
        text=f"Pergunta {n}?",
        purpose="Ver se avalia.",
        look_for=["Critério A", "Critério B", "Critério C"],
        follow_ups=[],
        targets_concern=None,
    )
    return GoldenItem(
        item_id=f"gq-tech-0{n}-{variant}",
        question=question,
        answer_text=f"Resposta {n}.",
        variant=variant,
        paraphrase_of=None,
        human_score=score,
        generated_by="groq:x|synthetic_candidate@v4",
    )


def _inputs(*values: str) -> Callable[[str], str]:
    it: Iterator[str] = iter(values)
    return lambda _prompt: next(it)


@pytest.fixture
def dataset(tmp_path: Path) -> Path:
    path = tmp_path / "golden.jsonl"
    gio.save_items([_item(1), _item(2), _item(3)], path)
    return path


def test_save_and_load_roundtrip(dataset: Path) -> None:
    assert [i.item_id for i in gio.load_items(dataset)] == [
        "gq-tech-01-level_5",
        "gq-tech-02-level_5",
        "gq-tech-03-level_5",
    ]


def test_save_invalid_item_keeps_original(dataset: Path) -> None:
    before = dataset.read_text(encoding="utf-8")
    bad = _item(1).model_copy(update={"human_score": 9})
    with pytest.raises(ValidationError):
        gio.save_items([bad], dataset)
    assert dataset.read_text(encoding="utf-8") == before


def test_render_is_blind() -> None:
    item = _item(1).model_copy(update={"paraphrase_of": "gq-tech-01-level_3"})
    text = lg.render_item(item, 1, 70)
    for expected in ("Pergunta 1?", "Critério A", "Critério B", "Resposta 1."):
        assert expected in text
    for hidden in ("level_5", "gq-tech-01", "level_3"):
        assert hidden not in text


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1", 1),
        ("5", 5),
        (" 3 ", 3),
        ("q", "quit"),
        ("0", None),
        ("6", None),
        ("x", None),
        ("", None),
    ],
)
def test_parse_score(raw: str, expected: int | str | None) -> None:
    assert lg.parse_score(raw) == expected


def test_order_is_deterministic_and_shuffled() -> None:
    items = [_item(n % 9 + 1, v) for n, v in enumerate(["level_5", "level_4"] * 10)]
    first = lg.presentation_order(items)
    assert first == lg.presentation_order(items)
    assert first != sorted(first)
    assert sorted(first) == list(range(20))


def test_order_skips_scored_items() -> None:
    items = [_item(1, score=3), _item(2), _item(3, score=1)]
    assert lg.presentation_order(items) == [1]


def test_valid_score_then_quit(dataset: Path) -> None:
    first = lg.presentation_order(gio.load_items(dataset))[0]
    assert lg.main([], input_fn=_inputs("4", "q"), path=dataset) == 0
    scores = [i.human_score for i in gio.load_items(dataset)]
    assert scores[first] == 4
    assert scores.count(None) == 2


def test_invalid_inputs_are_rejected(dataset: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert lg.main([], input_fn=_inputs("0", "6", "x", "", "3", "q"), path=dataset) == 0
    scores = [i.human_score for i in gio.load_items(dataset)]
    assert sorted(s for s in scores if s is not None) == [3]
    assert capsys.readouterr().out.count(lg.INVALID_MSG) == 4


def test_resume_only_shows_unscored(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "golden.jsonl"
    gio.save_items([_item(1, score=2), _item(2), _item(3, score=4)], path)
    assert lg.main([], input_fn=_inputs("5"), path=path) == 0
    assert [i.human_score for i in gio.load_items(path)] == [2, 5, 4]
    out = capsys.readouterr().out
    assert "Pergunta 2?" in out and "Pergunta 1?" not in out


def test_all_scored_exits_clean(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "golden.jsonl"
    gio.save_items([_item(1, score=2)], path)
    before = path.read_text(encoding="utf-8")
    assert lg.main([], input_fn=_inputs(), path=path) == 0
    assert lg.NOTHING_MSG in capsys.readouterr().out
    assert path.read_text(encoding="utf-8") == before
