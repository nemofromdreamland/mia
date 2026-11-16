from datetime import UTC, datetime
from decimal import Decimal

from mia.repo_dynamo import (
    item_to_session,
    item_to_turn,
    session_to_item,
    turn_to_item,
)
from mia.schemas import AnswerScore, Session, ToolDecision, Turn

T0 = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
T1 = datetime(2026, 11, 16, 12, 30, tzinfo=UTC)


def full_session() -> Session:
    return Session(
        visitor_id="local",
        session_id="01SESSION",
        case_id="caso-a",
        case_version=2,
        candidate_no=7,
        status="completed",
        persona="technical",
        language="pt-BR",
        mode="text",
        job_title="Engenheira de Prompt",
        fit_score=80,
        overall_score=3.75,
        competency_scores={"comunicação": 4.5, "python": 3.0},
        headline="Boa comunicação.",
        prompt_versions={"interviewer": 2},
        created_at=T0,
        updated_at=T1,
        started_at=T0,
        ended_at=T1,
    )


def full_turn() -> Turn:
    return Turn(
        session_id="01SESSION",
        turn_no=3,
        question_id="q2",
        interviewer_text="Fale de um projeto.",
        answer_text="Fiz um RAG.",
        is_follow_up=True,
        decision=ToolDecision(action="follow_up", follow_up_text="Qual?", reason="vago"),
        score=AnswerScore(
            score=4,
            criteria_met=["exemplo"],
            evidence_quotes=["Fiz um RAG."],
            justification="ok",
            quotes_verified=True,
        ),
        latency_ms=850,
        created_at=T0,
    )


def test_session_round_trip() -> None:
    session = full_session()
    assert item_to_session(session_to_item(session)) == session


def test_session_item_types() -> None:
    item = session_to_item(full_session())
    assert item["overall_score"] == Decimal("3.75")
    assert item["competency_scores"]["comunicação"] == Decimal("4.5")
    assert item["created_at"] == "2026-11-16T12:00:00+00:00"
    assert item["ended_at"] == "2026-11-16T12:30:00+00:00"
    assert all(not isinstance(v, float) for v in item.values())


def test_session_item_omits_none() -> None:
    minimal = Session(
        visitor_id="local",
        session_id="01MIN",
        status="ready",
        persona="hr",
        language="pt-BR",
        mode="text",
        created_at=T0,
        updated_at=T0,
    )
    item = session_to_item(minimal)
    assert None not in item.values()
    assert "ended_at" not in item and "case_id" not in item
    assert item_to_session(item) == minimal


def test_turn_round_trip() -> None:
    turn = full_turn()
    item = turn_to_item(turn)
    assert item["created_at"] == "2026-11-16T12:00:00+00:00"
    assert item_to_turn(item) == turn


def test_turn_item_omits_none() -> None:
    turn = Turn(session_id="01S", turn_no=1, question_id="q1", interviewer_text="Oi", created_at=T0)
    item = turn_to_item(turn)
    assert None not in item.values()
    assert item_to_turn(item) == turn
