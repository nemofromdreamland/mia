"""Tests for the judge cassette recorder (task 2.10, step 1)."""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

from mia.pii import mask_text
from mia.schemas import GoldenItem

ROOT = Path(__file__).resolve().parents[1]


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "record_judge_cassette", ROOT / "scripts" / "record_judge_cassette.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["record_judge_cassette"] = module
    spec.loader.exec_module(module)
    return module


rec = _load()


def _golden() -> list[GoldenItem]:
    path = ROOT / "evals" / "datasets" / "judge_golden.jsonl"
    return [
        GoldenItem.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _items(n: int) -> list[GoldenItem]:
    return [i for i in _golden() if i.human_score is not None][:n]


def _output(item: GoldenItem) -> str:
    return json.dumps(
        {
            "score": item.human_score,
            "criteria_met": [item.question.look_for[0]],
            "evidence_quotes": [],
            "justification": "ok",
        },
        ensure_ascii=False,
    )


def _record(item: GoldenItem, *, version: int = 1, output: str | None = None) -> dict:
    return {
        "run_id": f"r-{item.item_id}-{version}",
        "experiment": "exp",
        "session_id": None,
        "prompt_name": "judge",
        "prompt_version": version,
        "provider": "bedrock",
        "model": "m",
        "params": {},
        "input_hash": "h",
        "input": {"question": item.question.text, "answer": mask_text(item.answer_text)},
        "output_raw": output if output is not None else _output(item),
        "output_parsed": None,
        "json_valid_first_try": True,
        "repaired": False,
        "input_tokens": 1,
        "output_tokens": 1,
        "latency_ms": 1,
        "cost_usd": 0.0,
        "error": None,
        "created_at": "2026-11-16T12:00:00Z",
    }


def _write_runs(path: Path, records: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return path


def _patch_golden(monkeypatch: pytest.MonkeyPatch, items: list[GoldenItem]) -> None:
    monkeypatch.setattr(rec, "load_golden", lambda path=None: items)


def test_match_records_one_per_item() -> None:
    items = _items(2)
    records = [rec.RunRecord.model_validate(_record(i)) for i in items]
    matched = rec.match_records(items, records, prompt_version=1)
    assert {k: len(v) for k, v in matched.items()} == {i.item_id: 1 for i in items}


def test_match_records_filters_prompt_version() -> None:
    (item,) = _items(1)
    v1 = rec.RunRecord.model_validate(_record(item, version=1, output="v1"))
    v2 = rec.RunRecord.model_validate(_record(item, version=2, output="v2"))
    matched = rec.match_records([item], [v1, v2], prompt_version=2)
    assert [r.output_raw for r in matched[item.item_id]] == ["v2"]


def test_main_writes_cassette_with_reference_metrics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    items = _items(3)
    _patch_golden(monkeypatch, items)
    runs = _write_runs(tmp_path / "runs.jsonl", [_record(i) for i in items])
    out = tmp_path / "cassette.jsonl"
    code = rec.main(
        ["--runs", str(runs), "--experiment", "exp", "--prompt-version", "1", "--out", str(out)]
    )
    assert code == 0
    header, cassette = rec.load_cassette(out)
    assert [c.item_id for c in cassette] == [i.item_id for i in items]
    assert all(c.output for c in cassette)
    assert header.prompt_version == 1
    assert header.source_run == "runs.jsonl"
    assert header.within_one_pct == 100.0


def test_main_fails_when_item_has_no_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    items = _items(3)
    _patch_golden(monkeypatch, items)
    runs = _write_runs(tmp_path / "runs.jsonl", [_record(i) for i in items[:2]])
    out = tmp_path / "cassette.jsonl"
    code = rec.main(
        ["--runs", str(runs), "--experiment", "exp", "--prompt-version", "1", "--out", str(out)]
    )
    assert code == 1
    assert items[2].item_id in capsys.readouterr().err
    assert not out.exists()


def test_main_fails_on_duplicate_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    items = _items(2)
    _patch_golden(monkeypatch, items)
    records = [_record(i) for i in items] + [_record(items[0])]
    runs = _write_runs(tmp_path / "runs.jsonl", records)
    out = tmp_path / "cassette.jsonl"
    code = rec.main(
        ["--runs", str(runs), "--experiment", "exp", "--prompt-version", "1", "--out", str(out)]
    )
    assert code == 1
    assert items[0].item_id in capsys.readouterr().err
    assert not out.exists()


def test_replay_item_is_offline(tmp_path: Path) -> None:
    (item,) = _items(1)
    score = rec.replay_item(item, _output(item), tmp_path, prompt_version=1)
    assert score.score == item.human_score
    assert score.quotes_verified is True
