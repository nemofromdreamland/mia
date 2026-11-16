from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import Mock

import boto3
import pytest
from botocore.exceptions import ClientError
from dynamo_tables import create_tables
from moto import mock_aws

from mia.repo_dynamo import (
    DynamoSessionRepository,
    item_to_session,
    item_to_turn,
    session_to_item,
    turn_to_item,
)
from mia.repositories import RepositoryError, SessionRepository
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


@pytest.fixture
def tables(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[Any, Any]]:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    with mock_aws():
        yield create_tables(boto3.resource("dynamodb", region_name="us-east-1"))


def _session() -> Session:
    return full_session().model_copy(update={"status": "ready", "ended_at": None})


def test_follows_protocol(tables: tuple[Any, Any]) -> None:
    assert isinstance(DynamoSessionRepository(*tables), SessionRepository)


@pytest.mark.parametrize("changes", [{"status": "zzz"}, {"unknown": "value"}])
def test_update_rejects_invalid_changes_before_dynamo_io(changes: dict[str, Any]) -> None:
    sessions = Mock()
    sessions.get_item.side_effect = AssertionError("DynamoDB called before validation")
    repo = DynamoSessionRepository(sessions, Mock())

    with pytest.raises(ValueError):
        repo.update_session(
            "local",
            "01SESSION",
            expected_status="preparing",
            changes=changes,
        )

    sessions.get_item.assert_not_called()


def test_list_turns_follows_pagination(tables: tuple[Any, Any]) -> None:
    sessions, turns = tables
    repo = DynamoSessionRepository(sessions, turns)
    repo.create_session(_session())
    for no in range(1, 31):
        repo.put_turn(
            "local",
            Turn(
                session_id="01SESSION",
                turn_no=no,
                question_id="q",
                interviewer_text="x",
                created_at=T0,
            ),
        )

    class SmallPages:
        """Wraps a table forcing tiny pages, so LastEvaluatedKey must be followed."""

        def __getattr__(self, name: str) -> Any:
            return getattr(turns, name)

        def query(self, **kwargs: Any) -> Any:
            return turns.query(Limit=7, **kwargs)

    paged = DynamoSessionRepository(sessions, SmallPages())
    assert [t.turn_no for t in paged.list_turns("local", "01SESSION")] == list(range(1, 31))


def test_unexpected_client_error_becomes_repository_error(tables: tuple[Any, Any]) -> None:
    class Broken:
        def query(self, **kwargs: Any) -> Any:
            raise ClientError({"Error": {"Code": "ProvisionedThroughputExceeded"}}, "Query")

        def scan(self, **kwargs: Any) -> Any:
            raise ClientError({"Error": {"Code": "ProvisionedThroughputExceeded"}}, "Scan")

    repo = DynamoSessionRepository(Broken(), Broken())
    with pytest.raises(RepositoryError):
        repo.list_sessions("local")
    with pytest.raises(RepositoryError):
        repo.list_completed()
    with pytest.raises(RepositoryError):
        repo.list_completed("caso-a")
