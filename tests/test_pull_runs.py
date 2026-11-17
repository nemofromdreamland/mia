"""Production RunRecords: stdout line in llm.py and pull back into runs/ (task 4.7b)."""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from mia import llm
from mia.schemas import RunRecord

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import pull_runs  # noqa: E402


def record(run_id: str = "r1", session: str | None = "S1", cost: float = 0.01) -> RunRecord:
    return RunRecord(
        run_id=run_id,
        experiment=None,
        session_id=session,
        prompt_name="interviewer",
        prompt_version=3,
        provider="bedrock",
        model="us.anthropic.claude-haiku-4-5-20251001-v1:0",
        params={},
        input_hash="h",
        input={},
        output_raw="ok",
        output_parsed=None,
        json_valid_first_try=None,
        repaired=None,
        input_tokens=100,
        output_tokens=20,
        latency_ms=900,
        cost_usd=cost,
        error=None,
        created_at=datetime(2026, 11, 17, 18, 0, tzinfo=UTC),
    )


def line(rec: RunRecord) -> str:
    return llm.RUN_RECORD_MARKER + rec.model_dump_json()


# ---------- R1: llm.py ----------


def test_stdout_line_when_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(llm.RUNS_STDOUT_ENV, "1")
    path = llm.append_run_record(record(), runs_dir=tmp_path)
    assert path.exists()
    out = capsys.readouterr().out.strip()
    assert out.startswith(llm.RUN_RECORD_MARKER)
    assert RunRecord.model_validate_json(out.removeprefix(llm.RUN_RECORD_MARKER)).run_id == "r1"


def test_no_stdout_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(llm.RUNS_STDOUT_ENV, raising=False)
    llm.append_run_record(record(), runs_dir=tmp_path)
    assert capsys.readouterr().out == ""


# ---------- R3, R4: pull_runs.py ----------


def test_parse_events() -> None:
    messages = [
        line(record("a")),
        line(record("b")),
        llm.RUN_RECORD_MARKER + "{broken",
        "INFO: GET /ping",
    ]
    valid, invalid = pull_runs.parse_events(messages)
    assert [r.run_id for r in valid] == ["a", "b"]
    assert invalid == 1


def test_write_records_names_and_dedupes(tmp_path: Path) -> None:
    existing = tmp_path / "2026-11-17_aws-adhoc.jsonl"
    existing.write_text(record("a").model_dump_json() + "\n", encoding="utf-8")
    known = pull_runs.known_run_ids(tmp_path)
    assert known == {"a"}
    new = pull_runs.write_records([record("a"), record("b"), record("b")], tmp_path, known)
    assert [r.run_id for r in new] == ["b"]
    lines = existing.read_text(encoding="utf-8").splitlines()
    assert [json.loads(x)["run_id"] for x in lines] == ["a", "b"]


def test_summary_per_session() -> None:
    text = pull_runs.summary(
        [record("a", "S1", 0.01), record("b", "S1", 0.02), record("c", "S2", 0.005)]
    )
    assert "3 chamadas" in text
    assert "US$ 0.0350" in text
    assert "S1: 2 chamadas, US$ 0.0300" in text and "S2: 1 chamadas, US$ 0.0050" in text


class FakeLogs:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def describe_log_groups(self, logGroupNamePrefix: str) -> dict:  # noqa: N803
        return {"logGroups": [{"logGroupName": logGroupNamePrefix + "X-live"}]}

    def filter_log_events(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        if "nextToken" not in kwargs:
            return {"events": [{"message": line(record("a"))}], "nextToken": "t"}
        return {"events": [{"message": line(record("b"))}]}


def test_fetch_messages_paginates_with_marker_filter() -> None:
    logs = FakeLogs()
    messages = pull_runs.fetch_messages(logs, "/aws/bedrock-agentcore/runtimes/mia_backend-")
    assert len(messages) == 2
    assert logs.calls[0]["filterPattern"] == '"MIA_RUN_RECORD"'


def test_main_writes_and_prints(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert pull_runs.main(["--runs-dir", str(tmp_path)], logs=FakeLogs()) == 0
    assert (tmp_path / "2026-11-17_aws-adhoc.jsonl").exists()
    assert "2 chamadas" in capsys.readouterr().out


def test_runtime_gets_runs_stdout_flag() -> None:
    text = (Path(__file__).resolve().parent.parent / "infra" / "agentcore.tf").read_text(
        encoding="utf-8"
    )
    assert 'MIA_RUNS_STDOUT         = "1"' in text or 'MIA_RUNS_STDOUT = "1"' in " ".join(
        text.split()
    )
