"""Tests for scripts/eval_sets_io.py (task 2.4, step 1)."""

import importlib.util
from collections import Counter
from pathlib import Path
from types import ModuleType

import pytest
from pydantic import BaseModel, ValidationError

SCRIPTS = Path(__file__).parents[1] / "scripts"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("eval_sets_io", SCRIPTS / "eval_sets_io.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


io = _load()


class Row(BaseModel):
    item_id: str
    group: str
    split: str | None = None


def _rows() -> list[Row]:
    return [Row(item_id=f"{g}-{i}", group=g) for g in ("a", "b") for i in range(5)]


def test_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "set.jsonl"
    rows = _rows()[:3]
    io.save_jsonl(rows, path)
    assert io.load_jsonl(path, Row) == rows
    assert list(tmp_path.iterdir()) == [path]


def test_load_skips_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "set.jsonl"
    path.write_text('{"item_id": "x", "group": "a"}\n\n', encoding="utf-8")
    assert [r.item_id for r in io.load_jsonl(path, Row)] == ["x"]


def test_load_reports_line_number(tmp_path: Path) -> None:
    path = tmp_path / "set.jsonl"
    path.write_text('{"item_id": "x", "group": "a"}\n{broken\n', encoding="utf-8")
    with pytest.raises(ValueError, match="line 2"):
        io.load_jsonl(path, Row)


def test_load_reports_schema_error_line(tmp_path: Path) -> None:
    path = tmp_path / "set.jsonl"
    path.write_text('{"item_id": "x"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="line 1"):
        io.load_jsonl(path, Row)


def test_save_revalidates(tmp_path: Path) -> None:
    bad = Row.model_construct(item_id="x", group=123)
    with pytest.raises(ValidationError):
        io.save_jsonl([bad], tmp_path / "set.jsonl")
    assert list(tmp_path.iterdir()) == []


def test_assign_splits_70_30_per_stratum() -> None:
    result = io.assign_splits(_rows(), lambda r: r.group, seed=1)
    counts = Counter((r.group, r.split) for r in result)
    for group in ("a", "b"):
        assert counts[(group, "dev")] + counts[(group, "test")] == 5
        assert counts[(group, "dev")] in (3, 4)
    assert [r.item_id for r in result] == [r.item_id for r in _rows()]


def test_assign_splits_is_deterministic() -> None:
    first = io.assign_splits(_rows(), lambda r: r.group, seed=7)
    second = io.assign_splits(_rows(), lambda r: r.group, seed=7)
    assert [r.split for r in first] == [r.split for r in second]


def test_assign_splits_ten_items_one_stratum() -> None:
    rows = [Row(item_id=str(i), group="a") for i in range(10)]
    result = io.assign_splits(rows, lambda r: r.group, seed=3)
    assert Counter(r.split for r in result) == {"dev": 7, "test": 3}


def test_assign_splits_does_not_mutate_input() -> None:
    rows = _rows()
    io.assign_splits(rows, lambda r: r.group, seed=1)
    assert all(r.split is None for r in rows)
