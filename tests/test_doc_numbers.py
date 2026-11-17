"""Tests for scripts/doc_numbers.py (task 6.4, step 2)."""

import json
from pathlib import Path

import pytest

from scripts.doc_numbers import (
    main,
    md_tables,
    production_summary,
    row,
    voice_first_audio,
)

MD = """# Métricas — x

## Concordância juiz × humano

| Modelo | Split | n | Kappa |
|---|---|---|---|
| judge-v1 | test (oficial) | 21 | 0.61 |
| judge-v2 | test (oficial) | 21 | 0.82 |

## Vazia

| Modelo | n |
|---|---|
"""


def _run(prompt: str, cost: float, **extra: object) -> str:
    record = {
        "prompt_name": prompt,
        "cost_usd": cost,
        "input_tokens": 10,
        "output_tokens": 5,
        "latency_ms": 100,
        "error": None,
        "json_valid_first_try": True,
        "params": {},
        "session_id": None,
    }
    record.update(extra)
    return json.dumps(record)


def test_md_tables_parses_sections(tmp_path: Path) -> None:
    path = tmp_path / "r.md"
    path.write_text(MD, encoding="utf-8")
    tables = md_tables(path)
    assert tables["Concordância juiz × humano"][1]["Kappa"] == "0.82"
    assert tables["Vazia"] == []


def test_row_finds_by_column_values(tmp_path: Path) -> None:
    path = tmp_path / "r.md"
    path.write_text(MD, encoding="utf-8")
    table = md_tables(path)["Concordância juiz × humano"]
    assert row(table, Modelo="judge-v2", Split="test (oficial)")["Kappa"] == "0.82"


def test_row_missing_raises(tmp_path: Path) -> None:
    path = tmp_path / "r.md"
    path.write_text(MD, encoding="utf-8")
    with pytest.raises(KeyError):
        row(md_tables(path)["Concordância juiz × humano"], Modelo="judge-v9")


def test_voice_first_audio_median_and_p90() -> None:
    records = [
        {"prompt_name": "voice_interviewer", "params": {"first_audio_ms": ms}}
        for ms in (1000, 2000, 3000)
    ]
    records.append({"prompt_name": "voice_interviewer", "params": {"first_audio_ms": None}})
    median, p90, n = voice_first_audio(records)
    assert (median, n) == (2.0, 3)
    assert p90 == pytest.approx(2.8)


def test_voice_first_audio_without_records_raises() -> None:
    with pytest.raises(ValueError, match="voice_interviewer"):
        voice_first_audio([{"prompt_name": "judge", "params": {}}])


def test_production_summary_aggregates_without_text(tmp_path: Path) -> None:
    runs = tmp_path / "2026-11-17_aws-adhoc.jsonl"
    lines = [
        _run("judge", 0.01, input={"answer": "segredo do visitante"}),
        _run("report", 0.02),
        _run("report", 0.02),
        _run("voice_interviewer", 0.5, params={"first_audio_ms": 1200}),
    ]
    runs.write_text("\n".join(lines) + "\n", encoding="utf-8")
    text = production_summary(tmp_path)
    assert "segredo" not in text
    assert "| Text calls | 3 |" in text
    assert "| Completed text interviews (report calls) | 2 |" in text
    assert "| Text cost per completed interview, all calls / reports (USD) | 0.0250 |" in text
    assert "| Voice time to first audio, median (s) | 1.20 |" in text


def test_main_prints_table(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--results", "results"]) == 0
    out = capsys.readouterr().out
    assert "judge v2 kappa (test)" in out
    assert "0.82" in out
    assert "judge v1 within ±1 (test) | 76.2%" in out
    assert "robustness attack types | 5" in out
