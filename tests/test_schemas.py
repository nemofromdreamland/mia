from datetime import UTC, datetime
from typing import Any, get_args

import pytest
from pydantic import ValidationError

from mia.schemas import (
    AnswerScore,
    Case,
    CaseSummary,
    CompetencyScore,
    Evidence,
    Improvement,
    InterviewPlan,
    Language,
    Level,
    Mode,
    Persona,
    Phase,
    PublicTurn,
    Question,
    Report,
    RunRecord,
    Screening,
    SessionStatus,
    ToolDecision,
    Turn,
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


# ---------- Interview + Report ----------

NOW = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)


def _decision_fields(**overrides: Any) -> dict[str, Any]:
    return {"action": "next_question", "reason": "answer was complete", **overrides}


def _answer_score_fields(**overrides: Any) -> dict[str, Any]:
    return {
        "score": 3,
        "criteria_met": ["a"],
        "evidence_quotes": ["I did X"],
        "justification": "partial answer",
        **overrides,
    }


def _turn_fields(**overrides: Any) -> dict[str, Any]:
    return {
        "session_id": "s1",
        "turn_no": 1,
        "question_id": "q1",
        "interviewer_text": "Tell me about yourself.",
        "created_at": NOW,
        **overrides,
    }


def _report_fields(**overrides: Any) -> dict[str, Any]:
    return {
        "overall_score": 3.5,
        "competencies": [{"competency": "python", "score": 4.0, "summary": "solid"}],
        "strengths": ["clear"],
        "improvements": [{"question_id": "q1", "issue": "vague", "stronger_answer": "..."}],
        **overrides,
    }


def test_tool_decision_rejects_unknown_action() -> None:
    with pytest.raises(ValidationError):
        ToolDecision(**_decision_fields(action="skip"))


def test_tool_decision_follow_up_text_defaults_to_none() -> None:
    assert ToolDecision(**_decision_fields()).follow_up_text is None


@pytest.mark.parametrize("value", [0, 6])
def test_answer_score_rejects_score_outside_1_5(value: int) -> None:
    with pytest.raises(ValidationError):
        AnswerScore(**_answer_score_fields(score=value))


@pytest.mark.parametrize("value", [1, 5])
def test_answer_score_accepts_score_limits(value: int) -> None:
    assert AnswerScore(**_answer_score_fields(score=value)).score == value


def test_answer_score_accepts_empty_lists_and_defaults_quotes_verified() -> None:
    score = AnswerScore(**_answer_score_fields(criteria_met=[], evidence_quotes=[]))
    assert score.criteria_met == [] and score.evidence_quotes == []
    assert score.quotes_verified is None


def test_turn_requires_created_at() -> None:
    fields = _turn_fields()
    del fields["created_at"]
    with pytest.raises(ValidationError):
        Turn(**fields)


def test_turn_minimal_uses_defaults() -> None:
    turn = Turn(**_turn_fields())
    assert turn.is_follow_up is False
    assert turn.answer_text is None and turn.decision is None and turn.score is None
    assert turn.latency_ms is None


def test_public_turn_dump_hides_scoring_fields() -> None:
    fields = {
        "turn_no": 1,
        "question_id": "q1",
        "interviewer_text": "Hi",
        "created_at": NOW,
    }
    dumped = PublicTurn(**fields).model_dump()
    assert set(dumped) == {
        "turn_no",
        "question_id",
        "interviewer_text",
        "answer_text",
        "created_at",
    }


@pytest.mark.parametrize("value", [0.5, 0.99, 5.01])
def test_competency_score_rejects_score_outside_1_5(value: float) -> None:
    with pytest.raises(ValidationError):
        CompetencyScore(competency="python", score=value, summary="x")


@pytest.mark.parametrize("value", [0.99, 5.01])
def test_report_rejects_overall_score_outside_1_5(value: float) -> None:
    with pytest.raises(ValidationError):
        Report(**_report_fields(overall_score=value))


@pytest.mark.parametrize("value", [1.0, 3.5, 5.0])
def test_report_accepts_overall_score_limits_and_fractions(value: float) -> None:
    assert Report(**_report_fields(overall_score=value)).overall_score == value


def test_report_accepts_empty_lists() -> None:
    report = Report(**_report_fields(competencies=[], strengths=[], improvements=[]))
    assert report.competencies == [] and report.strengths == [] and report.improvements == []


def test_improvement_requires_stronger_answer() -> None:
    with pytest.raises(ValidationError):
        Improvement(question_id="q1", issue="vague")  # type: ignore[call-arg]


@pytest.mark.parametrize(
    "model",
    [
        Turn(
            **_turn_fields(
                answer_text="I did X",
                decision=_decision_fields(),
                score=_answer_score_fields(),
            )
        ),
        Report(**_report_fields()),
    ],
    ids=["turn", "report"],
)
def test_interview_models_round_trip_through_json(model: Any) -> None:
    assert type(model).model_validate_json(model.model_dump_json()) == model

