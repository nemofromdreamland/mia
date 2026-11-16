"""Tests for the service layer (every model dependency is a fake)."""

from datetime import UTC, datetime, timedelta

import pytest

from mia.cases import CASES_DIR
from mia.repositories import (
    InMemoryCandidateCounter,
    InMemoryReportStore,
    InMemorySessionRepository,
)
from mia.schemas import Session, ToolDecision, Turn
from mia.service import (
    ServiceDeps,
    ServiceError,
    create_session,
    delete_session,
    get_session,
    list_cases,
    list_sessions,
    to_public,
)

T0 = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
VISITOR_A = "11111111-1111-4111-8111-111111111111"
VISITOR_B = "22222222-2222-4222-8222-222222222222"
CASE_ID = "software-intern"


class Calls:
    def __init__(self) -> None:
        self.writer = 0
        self.report = 0
        self.gate = 0


class Gate:
    def __init__(self, calls: Calls, error: ServiceError | None = None) -> None:
        self.calls = calls
        self.error = error

    def check(self, visitor_id: str) -> None:
        self.calls.gate += 1
        if self.error:
            raise self.error


def make_deps(gate_error: ServiceError | None = None, calls: Calls | None = None) -> ServiceDeps:
    calls = calls or Calls()
    tick = {"now": T0}

    def clock() -> datetime:
        tick["now"] += timedelta(seconds=1)
        return tick["now"]

    def writer_for(persona):
        def writer(phase, question, instruction, history) -> str:
            calls.writer += 1
            return question

        return writer

    def report(plan, turns):
        calls.report += 1
        raise AssertionError("report not expected")

    return ServiceDeps(
        repo=InMemorySessionRepository(clock=clock),
        reports=InMemoryReportStore(),
        counter=InMemoryCandidateCounter(),
        gate=Gate(calls, gate_error),
        decider=lambda q, a, s, t: ToolDecision(action="next_question", reason="ok"),
        writer_for=writer_for,
        scorer=lambda q, a: pytest.fail("scorer not expected"),
        report=report,
        clock=clock,
        cases_dir=CASES_DIR,
    )


def test_list_cases_counts_completed_sessions() -> None:
    deps = make_deps()
    session = create_session(deps, VISITOR_A, CASE_ID, "text")
    deps.repo.update_session(
        VISITOR_A,
        session.session_id,
        expected_status="ready",
        changes={"status": "completed", "overall_score": 4.0, "headline": "ok"},
    )

    summaries = list_cases(deps)

    assert len(summaries) == 5
    by_id = {s.case_id: s for s in summaries}
    assert by_id[CASE_ID].completed_sessions == 1
    assert sum(s.completed_sessions for s in summaries) == 1


def test_create_session_ready_with_case_data_and_no_model_call() -> None:
    calls = Calls()
    deps = make_deps(calls=calls)

    first = create_session(deps, VISITOR_A, CASE_ID, "text")
    second = create_session(deps, VISITOR_B, CASE_ID, "voice")

    assert first.status == "ready"
    assert first.visitor_id == VISITOR_A
    assert first.case_id == CASE_ID
    assert first.case_version is not None
    assert first.job_title and first.fit_score is not None
    assert (first.candidate_no, second.candidate_no) == (1, 2)
    assert second.mode == "voice"
    assert calls.writer == 0 and calls.report == 0
    assert deps.repo.get_session(VISITOR_A, first.session_id) == first


def test_create_session_unknown_case_is_invalid_input_and_nothing_is_written() -> None:
    deps = make_deps()

    with pytest.raises(ServiceError) as exc:
        create_session(deps, VISITOR_A, "xpto", "text")

    assert exc.value.code == "invalid_input"
    assert deps.repo.list_sessions(VISITOR_A) == []
    assert deps.counter.next(CASE_ID) == 1  # the counter did not advance


@pytest.mark.parametrize("code", ["quota_exceeded", "demo_paused"])
def test_create_session_gate_refusal_writes_nothing(code) -> None:
    deps = make_deps(gate_error=ServiceError(code, "no"))

    with pytest.raises(ServiceError) as exc:
        create_session(deps, VISITOR_A, CASE_ID, "text")

    assert exc.value.code == code
    assert deps.repo.list_sessions(VISITOR_A) == []
    assert deps.counter.next(CASE_ID) == 1


def test_list_sessions_only_own_newest_first() -> None:
    deps = make_deps()
    a1 = create_session(deps, VISITOR_A, CASE_ID, "text")
    create_session(deps, VISITOR_B, CASE_ID, "text")
    a2 = create_session(deps, VISITOR_A, "backend-python-jr", "text")

    result = list_sessions(deps, VISITOR_A)

    assert [s.session_id for s in result] == [a2.session_id, a1.session_id]


def test_get_session_ready_includes_screening_and_case_but_not_plan() -> None:
    deps = make_deps()
    session = create_session(deps, VISITOR_A, CASE_ID, "text")

    view = get_session(deps, VISITOR_A, session.session_id)

    assert view.session == session
    assert view.case is not None and view.case.case_id == CASE_ID
    assert view.screening is not None
    assert view.turns is None
    assert "questions" not in view.model_dump_json()


def test_get_session_in_progress_returns_public_turns_only() -> None:
    deps = make_deps()
    session = create_session(deps, VISITOR_A, CASE_ID, "text")
    deps.repo.update_session(
        VISITOR_A,
        session.session_id,
        expected_status="ready",
        changes={"status": "in_progress", "started_at": T0},
    )
    deps.repo.put_turn(
        VISITOR_A,
        Turn(
            session_id=session.session_id,
            turn_no=1,
            question_id="q1",
            interviewer_text="Olá",
            answer_text="Oi",
            is_follow_up=True,
            decision=ToolDecision(action="end", reason="x"),
            created_at=T0,
        ),
    )

    view = get_session(deps, VISITOR_A, session.session_id)

    assert view.turns is not None and len(view.turns) == 1
    dumped = view.model_dump_json()
    for private in ("score", "decision", "is_follow_up"):
        assert f'"{private}"' not in dumped
    assert view.case is None and view.screening is None


def test_to_public_drops_private_fields() -> None:
    turn = Turn(
        session_id="s",
        turn_no=2,
        question_id="q",
        interviewer_text="t",
        is_follow_up=True,
        created_at=T0,
    )

    public = to_public(turn)

    assert set(public.model_dump()) == {
        "turn_no",
        "question_id",
        "interviewer_text",
        "answer_text",
        "created_at",
    }


def test_other_visitor_gets_not_found() -> None:
    deps = make_deps()
    session = create_session(deps, VISITOR_A, CASE_ID, "text")

    for call in (get_session, delete_session):
        with pytest.raises(ServiceError) as exc:
            call(deps, VISITOR_B, session.session_id)
        assert exc.value.code == "not_found"


def test_missing_session_is_not_found() -> None:
    deps = make_deps()

    with pytest.raises(ServiceError) as exc:
        get_session(deps, VISITOR_A, "nope")

    assert exc.value.code == "not_found"


def test_delete_session_removes_session_and_report() -> None:
    deps = make_deps()
    session = create_session(deps, VISITOR_A, CASE_ID, "text")

    delete_session(deps, VISITOR_A, session.session_id)

    assert list_sessions(deps, VISITOR_A) == []
    with pytest.raises(ServiceError) as exc:
        get_session(deps, VISITOR_A, session.session_id)
    assert exc.value.code == "not_found"
    assert isinstance(session, Session)
