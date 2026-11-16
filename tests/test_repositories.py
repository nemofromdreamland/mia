from collections.abc import Iterator
from datetime import UTC, datetime

import boto3
import pytest
from dynamo_tables import create_tables
from moto import mock_aws

from mia.repo_dynamo import DynamoSessionRepository
from mia.repositories import (
    CandidateCounter,
    InMemoryCandidateCounter,
    InMemoryReportStore,
    InMemorySessionRepository,
    ReportStore,
    SessionConflictError,
    SessionNotFoundError,
    SessionRepository,
)
from mia.schemas import CandidateSummary, Report, Session, SummaryPoint, Turn

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
def memory_repo() -> InMemorySessionRepository:
    repository = InMemorySessionRepository(clock=lambda: T1)
    repository.create_session(make_session())
    return repository


@pytest.fixture(params=["memory", "dynamo"])
def repo(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Iterator[SessionRepository]:
    """Contract fixture: the same tests run against both implementations."""
    if request.param == "memory":
        repository: SessionRepository = InMemorySessionRepository(clock=lambda: T1)
        repository.create_session(make_session())
        yield repository
        return
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    with mock_aws():
        sessions, turns = create_tables(boto3.resource("dynamodb", region_name="us-east-1"))
        repository = DynamoSessionRepository(sessions, turns, clock=lambda: T1)
        repository.create_session(make_session())
        yield repository


def test_in_memory_repository_follows_protocol(memory_repo: InMemorySessionRepository) -> None:
    assert isinstance(memory_repo, SessionRepository)


def test_create_and_get_returns_equal_copy(repo: SessionRepository) -> None:
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


def test_other_visitor_cannot_see_session(repo: SessionRepository) -> None:
    with pytest.raises(SessionNotFoundError):
        repo.get_session("outro", "01SESSION")


def test_unknown_session_raises_not_found(repo: SessionRepository) -> None:
    with pytest.raises(SessionNotFoundError):
        repo.get_session("local", "NOPE")


def test_duplicate_session_id_raises_conflict(repo: SessionRepository) -> None:
    with pytest.raises(SessionConflictError):
        repo.create_session(make_session())


def test_update_with_wrong_expected_status_changes_nothing(
    repo: SessionRepository,
) -> None:
    with pytest.raises(SessionConflictError):
        repo.update_session(
            "local", "01SESSION", expected_status="ready", changes={"status": "in_progress"}
        )
    assert repo.get_session("local", "01SESSION") == make_session()


def test_update_applies_changes_and_updated_at(repo: SessionRepository) -> None:
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


def test_update_other_visitor_raises_not_found(repo: SessionRepository) -> None:
    with pytest.raises(SessionNotFoundError):
        repo.update_session("outro", "01SESSION", expected_status="preparing", changes={})


def test_update_rejects_invalid_value(repo: SessionRepository) -> None:
    with pytest.raises(ValueError):
        repo.update_session(
            "local", "01SESSION", expected_status="preparing", changes={"status": "zzz"}
        )
    assert repo.get_session("local", "01SESSION").status == "preparing"


def test_update_rejects_key_fields(repo: SessionRepository) -> None:
    with pytest.raises(ValueError):
        repo.update_session(
            "local", "01SESSION", expected_status="preparing", changes={"visitor_id": "x"}
        )


def test_turns_listed_in_order_and_upserted(memory_repo: InMemorySessionRepository) -> None:
    for no in (3, 1, 2):
        memory_repo.put_turn("local", make_turn(no))
    memory_repo.put_turn("local", make_turn(2, "Nova"))
    turns = memory_repo.list_turns("local", "01SESSION")
    assert [t.turn_no for t in turns] == [1, 2, 3]
    assert turns[1].interviewer_text == "Nova"


def test_list_turns_empty(memory_repo: InMemorySessionRepository) -> None:
    assert memory_repo.list_turns("local", "01SESSION") == []


def test_put_turn_other_visitor_raises_not_found(memory_repo: InMemorySessionRepository) -> None:
    with pytest.raises(SessionNotFoundError):
        memory_repo.put_turn("outro", make_turn(1))


def test_list_turns_other_visitor_raises_not_found(memory_repo: InMemorySessionRepository) -> None:
    with pytest.raises(SessionNotFoundError):
        memory_repo.list_turns("outro", "01SESSION")


def _completed(
    session_id: str, case_id: str | None = "case_a", visitor_id: str = "local"
) -> Session:
    return make_session(session_id, visitor_id).model_copy(
        update={"status": "completed", "case_id": case_id}
    )


def test_list_sessions_only_from_visitor_newest_first() -> None:
    repo = InMemorySessionRepository()
    old = make_session("01OLD", "a")
    new = make_session("01NEW", "a").model_copy(update={"created_at": T1})
    repo.create_session(old)
    repo.create_session(new)
    repo.create_session(make_session("01OTHER", "b"))
    assert [s.session_id for s in repo.list_sessions("a")] == ["01NEW", "01OLD"]
    assert repo.list_sessions("nobody") == []


def test_list_completed_filters_status_and_case(memory_repo: InMemorySessionRepository) -> None:
    memory_repo.create_session(_completed("01A1", "case_a", "a"))
    memory_repo.create_session(_completed("01B1", "case_b", "b"))
    memory_repo.create_session(make_session("01OPEN", "a"))
    assert {s.session_id for s in memory_repo.list_completed()} == {"01A1", "01B1"}
    assert [s.session_id for s in memory_repo.list_completed("case_a")] == ["01A1"]


def test_delete_session_removes_session_and_turns(memory_repo: InMemorySessionRepository) -> None:
    memory_repo.put_turn("local", make_turn(1))
    memory_repo.delete_session("local", "01SESSION")
    with pytest.raises(SessionNotFoundError):
        memory_repo.get_session("local", "01SESSION")
    with pytest.raises(SessionNotFoundError):
        memory_repo.list_turns("local", "01SESSION")
    assert memory_repo.list_sessions("local") == []


def test_delete_other_visitor_raises_not_found(memory_repo: InMemorySessionRepository) -> None:
    with pytest.raises(SessionNotFoundError):
        memory_repo.delete_session("intruder", "01SESSION")
    assert memory_repo.get_session("local", "01SESSION").session_id == "01SESSION"


def _report() -> tuple[Report, CandidateSummary]:
    point = SummaryPoint(point="Clareza", answer_quote="eu usaria")
    summary = CandidateSummary(
        headline="Boa base",
        summary="Resumo.",
        strengths=[point],
        concerns=[point],
        suggested_next_step="advance",
        next_step_reason="Motivo.",
    )
    report = Report(overall_score=4.0, competencies=[], strengths=[], improvements=[])
    return report, summary


def test_report_store_save_load_delete() -> None:
    store = InMemoryReportStore()
    assert isinstance(store, ReportStore)
    report, summary = _report()
    store.save("01S", report, summary)
    assert store.load("01S") == (report, summary)
    store.delete("01S")
    with pytest.raises(SessionNotFoundError):
        store.load("01S")
    store.delete("01S")  # deleting twice is harmless


def test_report_store_returns_copies() -> None:
    store = InMemoryReportStore()
    report, summary = _report()
    store.save("01S", report, summary)
    loaded, _ = store.load("01S")
    loaded.strengths.append("mutated")
    assert store.load("01S")[0].strengths == []


def test_candidate_counter_is_sequential_per_case() -> None:
    counter = InMemoryCandidateCounter()
    assert isinstance(counter, CandidateCounter)
    assert [counter.next("a"), counter.next("a"), counter.next("b")] == [1, 2, 1]
