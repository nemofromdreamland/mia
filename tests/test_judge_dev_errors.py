"""Tests for the dev-only judge error listing (task 2.9, step 2)."""

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "judge_dev_errors.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("judge_dev_errors", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


jde = _load()


def _result(
    item_id: str,
    split: str,
    human: int,
    judge: int | None,
    *,
    label: str = "haiku",
    quotes_verified: bool = True,
    error: str | None = None,
) -> dict:
    response: dict = {}
    if error:
        response["error"] = error
    else:
        response["output"] = json.dumps(
            {
                "score": judge,
                "justification": f"just {item_id}",
                "quotes_verified": quotes_verified,
            }
        )
    return {
        "provider": {"label": label},
        "response": response,
        "testCase": {
            "vars": {
                "item": {
                    "item_id": item_id,
                    "variant": "verbose",
                    "split": split,
                    "human_score": human,
                }
            }
        },
    }


def _export(tmp_path: Path, results: list[dict]) -> Path:
    path = tmp_path / "export.json"
    path.write_text(json.dumps({"results": {"results": results}}), encoding="utf-8")
    return path


def test_only_dev_items_are_listed(tmp_path: Path) -> None:
    path = _export(
        tmp_path,
        [
            _result("d1", "dev", 2, 4),
            _result("d2", "dev", 2, 5),
            _result("t1", "test", 2, 5),
            _result("t2", "test", 1, 5),
        ],
    )
    text = jde.render_errors(jde.dev_errors(path))
    assert "d1" in text and "d2" in text
    assert "t1" not in text and "t2" not in text


def test_min_gap_filters(tmp_path: Path) -> None:
    path = _export(
        tmp_path,
        [_result("g0", "dev", 3, 3), _result("g1", "dev", 3, 4), _result("g2", "dev", 3, 5)],
    )
    errors = jde.dev_errors(path, min_gap=2)
    assert [e.item_id for e in errors] == ["g2"]


def test_judge_error_appears_with_none_score(tmp_path: Path) -> None:
    path = _export(tmp_path, [_result("e1", "dev", 3, None, error="boom")])
    errors = jde.dev_errors(path)
    assert [(e.item_id, e.judge_score) for e in errors] == [("e1", None)]


def test_label_filter_and_dropped_quotes(tmp_path: Path) -> None:
    path = _export(
        tmp_path,
        [
            _result("a", "dev", 2, 4, label="haiku", quotes_verified=False),
            _result("b", "dev", 2, 4, label="other"),
        ],
    )
    errors = jde.dev_errors(path, label="haiku")
    assert [e.item_id for e in errors] == ["a"]
    assert errors[0].dropped_quotes == 1


def test_main_refuses_test_split(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _export(tmp_path, [_result("d1", "dev", 2, 4)])
    assert jde.main([str(path), "--split", "test"]) == 2
    assert "teste" in capsys.readouterr().err


def test_main_prints_dev_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _export(tmp_path, [_result("d1", "dev", 2, 4), _result("t1", "test", 2, 5)])
    assert jde.main([str(path)]) == 0
    out = capsys.readouterr().out
    assert "d1" in out and "t1" not in out
