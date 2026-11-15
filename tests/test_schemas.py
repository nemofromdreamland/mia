from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from mia.schemas import RunRecord


def _run_record_fields(**overrides: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "run_id": "3f2b9c1e8a7d4b6f9e0a1c2d3e4f5a6b",
        "experiment": "test",
        "session_id": None,
        "prompt_name": "smoke",
        "prompt_version": 1,
        "provider": "gemini",
        "model": "test-flash",
        "params": {"temperature": 0.2},
        "input_hash": "a" * 64,
        "input": {"question": "u"},
        "output_raw": '{"score": 4}',
        "output_parsed": {"score": 4},
        "json_valid_first_try": True,
        "repaired": False,
        "input_tokens": 12,
        "output_tokens": 3,
        "latency_ms": 250,
        "cost_usd": 0.0000024,
        "error": None,
        "created_at": datetime(2026, 11, 15, 12, 0, tzinfo=UTC),
    }
    fields.update(overrides)
    return fields


def test_run_record_accepts_valid_fields_and_round_trips_through_json() -> None:
    record = RunRecord(**_run_record_fields())

    assert RunRecord.model_validate_json(record.model_dump_json()) == record


def test_run_record_accepts_none_for_structured_output_fields_in_free_text_calls() -> None:
    record = RunRecord(
        **_run_record_fields(
            output_raw="olá",
            output_parsed=None,
            json_valid_first_try=None,
            repaired=None,
        )
    )

    dumped = record.model_dump_json()
    assert '"output_parsed":null' in dumped
    assert '"json_valid_first_try":null' in dumped
    assert '"repaired":null' in dumped


def test_run_record_rejects_unknown_provider() -> None:
    with pytest.raises(ValidationError):
        RunRecord(**_run_record_fields(provider="openai"))


def test_run_record_rejects_missing_required_field() -> None:
    fields = _run_record_fields()
    del fields["prompt_version"]

    with pytest.raises(ValidationError):
        RunRecord(**fields)
