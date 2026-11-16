from datetime import UTC, datetime

import pytest

from mia.repositories import (
    InMemorySessionRepository,
    SessionConflictError,
    SessionNotFoundError,
    SessionRepository,
)
from mia.schemas import Session, Turn

T0 = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
T1 = datetime(2026, 11, 16, 12, 5, tzinfo=UTC)


def make_session(session_id: str = "01SESSION", visitor_id: str = "local") -> Session:
    return Session(
        visitor_id=visitor_id,
        session_id=session_id,
        status="preparing",
        persona="technical",
        language="pt-BR",
        mode="text",
        created_at=T0,
        updated_at=T0,
    )


def make_turn(turn_no: int, text: str = "Pergunta", session_id: str = "01SESSION") -> Turn:
    return Turn(
        session_id=session_id,
        turn_no=turn_no,
        question_id="q1",
        interviewer_text=text,
        created_at=T0,
    )


@pytest.fixture
def repo() -> InMemorySessionRepository:
    repository = InMemorySessionRepository(clock=lambda: T1)
    repository.create_session(make_session())
    return repository


def test_in_memory_repository_follows_protocol(repo: InMemorySessionRepository) -> None:
    assert isinstance(repo, SessionRepository)


def test_create_and_get_returns_equal_copy(repo: InMemorySessionRepository) -> None:
    got = repo.get_session("local", "01SESSION")
    assert got == make_session()
    got.status = "failed"
    assert repo.get_session("local", "01SESSION").status == "preparing"


def test_create_stores_a_copy() -> None:
    repository = InMemorySessionRepository()
    session = make_session()
    repository.create_session(session)
    session.status = "failed"
    assert repository.get_session("local", "01SESSION").status == "preparing"


def test_other_visitor_cannot_see_session(repo: InMemorySessionRepository) -> None:
    with pytest.raises(SessionNotFoundError):
        repo.get_session("outro", "01SESSION")


def test_unknown_session_raises_not_found(repo: InMemorySessionRepository) -> None:
    with pytest.raises(SessionNotFoundError):
        repo.get_session("local", "NOPE")


def test_duplicate_session_id_raises_conflict(repo: InMemorySessionRepository) -> None:
    with pytest.raises(SessionConflictError):
        repo.create_session(make_session())


def test_update_with_wrong_expected_status_changes_nothing(
    repo: InMemorySessionRepository,
) -> None:
    with pytest.raises(SessionConflictError):
        repo.update_session(
            "local", "01SESSION", expected_status="ready", changes={"status": "in_progress"}
        )
    assert repo.get_session("local", "01SESSION") == make_session()


def test_update_applies_changes_and_updated_at(repo: InMemorySessionRepository) -> None:
    updated = repo.update_session(
        "local",
        "01SESSION",
        expected_status="preparing",
        changes={"status": "ready", "fit_score": 80},
    )
    assert updated.status == "ready"
    assert updated.fit_score == 80
    assert updated.updated_at == T1
    assert repo.get_session("local", "01SESSION") == updated


def test_update_other_visitor_raises_not_found(repo: InMemorySessionRepository) -> None:
    with pytest.raises(SessionNotFoundError):
        repo.update_session("outro", "01SESSION", expected_status="preparing", changes={})


def test_update_rejects_invalid_value(repo: InMemorySessionRepository) -> None:
    with pytest.raises(ValueError):
        repo.update_session(
            "local", "01SESSION", expected_status="preparing", changes={"status": "zzz"}
        )
    assert repo.get_session("local", "01SESSION").status == "preparing"


def test_update_rejects_key_fields(repo: InMemorySessionRepository) -> None:
    with pytest.raises(ValueError):
        repo.update_session(
            "local", "01SESSION", expected_status="preparing", changes={"visitor_id": "x"}
        )


def test_turns_listed_in_order_and_upserted(repo: InMemorySessionRepository) -> None:
    for no in (3, 1, 2):
        repo.put_turn("local", make_turn(no))
    repo.put_turn("local", make_turn(2, "Nova"))
    turns = repo.list_turns("local", "01SESSION")
    assert [t.turn_no for t in turns] == [1, 2, 3]
    assert turns[1].interviewer_text == "Nova"


def test_list_turns_empty(repo: InMemorySessionRepository) -> None:
    assert repo.list_turns("local", "01SESSION") == []


def test_put_turn_other_visitor_raises_not_found(repo: InMemorySessionRepository) -> None:
    with pytest.raises(SessionNotFoundError):
        repo.put_turn("outro", make_turn(1))


def test_list_turns_other_visitor_raises_not_found(repo: InMemorySessionRepository) -> None:
    with pytest.raises(SessionNotFoundError):
        repo.list_turns("outro", "01SESSION")
