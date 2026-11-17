"""Task 4.7b: copy the production RunRecords from CloudWatch into runs/.

The AgentCore container prints `MIA_RUN_RECORD <json>` for every model call (MIA_RUNS_STDOUT=1).
This script finds those lines, validates them as RunRecord and appends the new ones to
runs/<UTC date>_aws-<experiment or adhoc>.jsonl, then prints the cost per session.

Usage:
    uv run python scripts/pull_runs.py [--runs-dir runs]
"""

import argparse
import json
import sys
from collections import defaultdict
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import boto3
from pydantic import ValidationError

from mia.llm import RUN_RECORD_MARKER
from mia.schemas import RunRecord

ROOT = Path(__file__).resolve().parent.parent
LOG_PREFIX = "/aws/bedrock-agentcore/runtimes/mia_backend-"
FILE_PREFIX = "aws-"


def parse_events(messages: Iterable[str]) -> tuple[list[RunRecord], int]:
    """(valid records, invalid marker lines); lines without the marker are ignored."""
    valid: list[RunRecord] = []
    invalid = 0
    for message in messages:
        start = message.find(RUN_RECORD_MARKER)
        if start < 0:
            continue
        try:
            valid.append(RunRecord.model_validate_json(message[start + len(RUN_RECORD_MARKER) :]))
        except ValidationError:
            invalid += 1
    return valid, invalid


def _path(record: RunRecord, runs_dir: Path) -> Path:
    name = f"{record.created_at.date().isoformat()}_{FILE_PREFIX}{record.experiment or 'adhoc'}"
    return runs_dir / f"{name}.jsonl"


def known_run_ids(runs_dir: Path) -> set[str]:
    ids: set[str] = set()
    for path in runs_dir.glob(f"*_{FILE_PREFIX}*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                ids.add(json.loads(line)["run_id"])
    return ids


def write_records(records: list[RunRecord], runs_dir: Path, known: set[str]) -> list[RunRecord]:
    """Append records whose run_id is new; return them."""
    runs_dir.mkdir(parents=True, exist_ok=True)
    new: list[RunRecord] = []
    for record in sorted(records, key=lambda r: r.created_at):
        if record.run_id in known:
            continue
        known.add(record.run_id)
        with _path(record, runs_dir).open("a", encoding="utf-8") as file:
            file.write(record.model_dump_json() + "\n")
        new.append(record)
    return new


def summary(records: list[RunRecord]) -> str:
    by_session: dict[str, list[float]] = defaultdict(list)
    for record in records:
        by_session[record.session_id or "(sem sessão)"].append(record.cost_usd)
    total = sum(r.cost_usd for r in records)
    lines = [f"{len(records)} chamadas, US$ {total:.4f}"]
    for session, costs in sorted(by_session.items()):
        lines.append(f"  {session}: {len(costs)} chamadas, US$ {sum(costs):.4f}")
    return "\n".join(lines)


def fetch_messages(logs: Any, prefix: str) -> list[str]:
    messages: list[str] = []
    for group in logs.describe_log_groups(logGroupNamePrefix=prefix)["logGroups"]:
        kwargs: dict[str, Any] = {
            "logGroupName": group["logGroupName"],
            "filterPattern": '"MIA_RUN_RECORD"',
        }
        while True:
            page = logs.filter_log_events(**kwargs)
            messages += [event["message"] for event in page.get("events", [])]
            if not page.get("nextToken"):
                break
            kwargs["nextToken"] = page["nextToken"]
    return messages


def main(argv: Sequence[str] | None = None, logs: Any | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs-dir", type=Path, default=ROOT / "runs")
    args = parser.parse_args(argv)
    if logs is None:
        logs = boto3.Session(profile_name="mia", region_name="us-east-1").client("logs")
    valid, invalid = parse_events(fetch_messages(logs, LOG_PREFIX))
    new = write_records(valid, args.runs_dir, known_run_ids(args.runs_dir))
    print(f"Novas: {len(new)} · já existentes: {len(valid) - len(new)} · inválidas: {invalid}")
    print(summary(new))
    return 0


if __name__ == "__main__":
    sys.exit(main())
