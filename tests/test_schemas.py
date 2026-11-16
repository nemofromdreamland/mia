from datetime import UTC, datetime
from typing import Any, get_args

import pytest
from pydantic import ValidationError

from mia.schemas import (
    Case,
    CaseSummary,
    Evidence,
    InterviewPlan,
    Language,
    Level,
    Mode,
    Persona,
    Phase,
    Question,
    RunRecord,
    Screening,
    SessionStatus,
)


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


# ---------- Aliases ----------


def test_aliases_expose_exactly_the_backend_schema_values() -> None:
    assert get_args(Persona) == ("hr", "technical", "manager")
    assert get_args(Language) == ("pt-BR", "en-US")
    assert get_args(Mode) == ("text", "voice")
    assert get_args(Level) == ("internship", "junior", "mid")
    assert get_args(SessionStatus) == (
        "preparing",
        "ready",
        "in_progress",
        "scoring",
        "completed",
        "failed",
        "abandoned",
    )
    assert get_args(Phase) == (
        "opening",
        "projects",
        "technical",
        "behavioral",
        "candidate_questions",
        "closing",
    )


# ---------- Casos ----------


def _case_fields(**overrides: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "case_id": "rag-junior",
        "title": "Engenheira de IA Júnior",
        "company": "Acme Fictícia",
        "level": "junior",
        "persona": "technical",
        "blurb": "Vaga para construir um sistema de RAG.",
        "candidate_blurb": "Você é recém-formada com um projeto de RAG.",
        "estimated_minutes": 15,
        "version": 1,
    }
    fields.update(overrides)
    return fields


def test_case_defaults_language_to_pt_br() -> None:
    assert Case(**_case_fields()).language == "pt-BR"


@pytest.mark.parametrize("field, value", [("persona", "ceo"), ("level", "senior")])
def test_case_rejects_values_outside_literals(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        Case(**_case_fields(**{field: value}))


def test_case_summary_accepts_valid_fields() -> None:
    fields = _case_fields(completed_sessions=0)
    del fields["version"]

    summary = CaseSummary(**fields)

    assert summary.completed_sessions == 0


# ---------- Preparação ----------


def _evidence(n: int = 1) -> list[dict[str, str]]:
    return [{"point": f"ponto {i}", "cv_quote": f"trecho {i}"} for i in range(n)]


def _screening_fields(**overrides: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "job_title": "Engenheira de IA Júnior",
        "fit_score": 70,
        "strengths": _evidence(2),
        "concerns": _evidence(1),
        "missing_keywords": ["Kubernetes"],
        "competencies": ["RAG", "Python", "Comunicação"],
    }
    fields.update(overrides)
    return fields


def _question_fields(**overrides: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "id": "q1",
        "phase": "technical",
        "competency": "RAG",
        "text": "Como você avaliaria a qualidade do retrieval?",
        "purpose": "Verificar avaliação de RAG.",
        "look_for": ["métrica", "dataset", "trade-off"],
        "follow_ups": ["E se não houver rótulos?"],
    }
    fields.update(overrides)
    return fields


def _plan_fields(**overrides: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "persona": "technical",
        "language": "pt-BR",
        "estimated_minutes": 15,
        "questions": [_question_fields(id=f"q{i}") for i in range(4)],
    }
    fields.update(overrides)
    return fields


def test_evidence_requires_cv_quote() -> None:
    with pytest.raises(ValidationError):
        Evidence(point="ponto")


@pytest.mark.parametrize("value", [0, 100])
def test_screening_accepts_fit_score_limits(value: int) -> None:
    assert Screening(**_screening_fields(fit_score=value)).fit_score == value


@pytest.mark.parametrize("value", [-1, 101])
def test_screening_rejects_fit_score_outside_0_100(value: int) -> None:
    with pytest.raises(ValidationError):
        Screening(**_screening_fields(fit_score=value))


@pytest.mark.parametrize(
    "field, value",
    [
        ("strengths", []),
        ("concerns", []),
        ("strengths", _evidence(6)),
        ("concerns", _evidence(6)),
        ("competencies", ["a", "b"]),
        ("competencies", list("abcdefg")),
    ],
)
def test_screening_rejects_lists_outside_limits(field: str, value: list[Any]) -> None:
    with pytest.raises(ValidationError):
        Screening(**_screening_fields(**{field: value}))


@pytest.mark.parametrize("n", [3, 6])
def test_screening_accepts_competencies_limits(n: int) -> None:
    competencies = [f"c{i}" for i in range(n)]
    assert Screening(**_screening_fields(competencies=competencies)).competencies == competencies


def test_screening_accepts_empty_missing_keywords() -> None:
    assert Screening(**_screening_fields(missing_keywords=[])).missing_keywords == []


def test_question_defaults_targets_concern_to_none() -> None:
    assert Question(**_question_fields()).targets_concern is None


def test_question_rejects_unknown_phase() -> None:
    with pytest.raises(ValidationError):
        Question(**_question_fields(phase="intro"))


@pytest.mark.parametrize(
    "field, value",
    [
        ("look_for", ["a", "b"]),
        ("look_for", list("abcde")),
        ("follow_ups", list("abcd")),
    ],
)
def test_question_rejects_lists_outside_limits(field: str, value: list[str]) -> None:
    with pytest.raises(ValidationError):
        Question(**_question_fields(**{field: value}))


@pytest.mark.parametrize(
    "field, value",
    [
        ("look_for", list("abc")),
        ("look_for", list("abcd")),
        ("follow_ups", []),
        ("follow_ups", list("abc")),
    ],
)
def test_question_accepts_list_limits(field: str, value: list[str]) -> None:
    assert getattr(Question(**_question_fields(**{field: value})), field) == value


@pytest.mark.parametrize("value", [5, 45])
def test_plan_accepts_estimated_minutes_limits(value: int) -> None:
    assert InterviewPlan(**_plan_fields(estimated_minutes=value)).estimated_minutes == value


@pytest.mark.parametrize("value", [4, 46])
def test_plan_rejects_estimated_minutes_outside_5_45(value: int) -> None:
    with pytest.raises(ValidationError):
        InterviewPlan(**_plan_fields(estimated_minutes=value))


@pytest.mark.parametrize("n", [3, 13])
def test_plan_rejects_question_count_outside_4_12(n: int) -> None:
    questions = [_question_fields(id=f"q{i}") for i in range(n)]
    with pytest.raises(ValidationError):
        InterviewPlan(**_plan_fields(questions=questions))


@pytest.mark.parametrize("n", [4, 12])
def test_plan_accepts_question_count_limits(n: int) -> None:
    questions = [_question_fields(id=f"q{i}") for i in range(n)]
    assert len(InterviewPlan(**_plan_fields(questions=questions)).questions) == n


@pytest.mark.parametrize(
    "model",
    [
        Case(**_case_fields()),
        Screening(**_screening_fields()),
        InterviewPlan(**_plan_fields()),
    ],
    ids=["case", "screening", "plan"],
)
def test_preparation_models_round_trip_through_json(model: Any) -> None:
    assert type(model).model_validate_json(model.model_dump_json()) == model
