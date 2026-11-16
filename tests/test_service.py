"""Tests for the service layer (every model dependency is a fake)."""

from datetime import UTC, datetime, timedelta

import pytest

from mia.cases import CASES_DIR
from mia.report_graph import ReportError, ReportResult
from mia.repositories import (
    InMemoryCandidateCounter,
    InMemoryReportStore,
    InMemorySessionRepository,
)
from mia.schemas import (
    AnswerScore,
    CandidateSummary,
    CompetencyScore,
    Report,
    Session,
    SummaryPoint,
    ToolDecision,
    Turn,
)
from mia.service import (
    ServiceDeps,
    ServiceError,
    create_session,
    delete_session,
    end_interview,
    get_recruiter_candidate,
    get_report,
    get_session,
    list_cases,
    list_recruiter_candidates,
    list_sessions,
    send_answer,
    start_interview,
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


def make_deps(
    gate_error: ServiceError | None = None, calls: Calls | None = None, scorer=None
) -> ServiceDeps:
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
        scorer=scorer or (lambda q, a: pytest.fail("scorer not expected")),
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


# ---------- interview (step 3) ----------


def fake_score(question, answer) -> AnswerScore:
    return AnswerScore(score=4, criteria_met=[], evidence_quotes=[], justification="ok")


def started(deps: ServiceDeps) -> Session:
    session = create_session(deps, VISITOR_A, CASE_ID, "text")
    start_interview(deps, VISITOR_A, session.session_id)
    return session


def test_start_interview_returns_first_public_turn_and_moves_to_in_progress() -> None:
    deps = make_deps()
    session = create_session(deps, VISITOR_A, CASE_ID, "text")

    turn = start_interview(deps, VISITOR_A, session.session_id)

    assert turn.turn_no == 1
    saved = deps.repo.get_session(VISITOR_A, session.session_id)
    assert saved.status == "in_progress"
    assert saved.started_at is not None and saved.turn_count == 1
    assert saved.current_question_id == turn.question_id
    assert len(deps.repo.list_turns(VISITOR_A, session.session_id)) == 1
    assert "decision" not in turn.model_dump()


def test_start_interview_twice_is_invalid_state() -> None:
    deps = make_deps()
    session = started(deps)

    with pytest.raises(ServiceError) as exc:
        start_interview(deps, VISITOR_A, session.session_id)

    assert exc.value.code == "invalid_state"


def test_send_answer_outside_in_progress_is_invalid_state() -> None:
    deps = make_deps()
    session = create_session(deps, VISITOR_A, CASE_ID, "text")  # ready

    with pytest.raises(ServiceError) as exc:
        send_answer(deps, VISITOR_A, session.session_id, "oi")

    assert exc.value.code == "invalid_state"


@pytest.mark.parametrize("text", ["", "   ", "x" * 4001])
def test_send_answer_invalid_input_saves_nothing(text) -> None:
    deps = make_deps(scorer=fake_score)
    session = started(deps)

    with pytest.raises(ServiceError) as exc:
        send_answer(deps, VISITOR_A, session.session_id, text)

    assert exc.value.code == "invalid_input"
    turns = deps.repo.list_turns(VISITOR_A, session.session_id)
    assert len(turns) == 1 and turns[0].answer_text is None


def test_send_answer_session_limit_by_turns_saves_nothing() -> None:
    deps = make_deps(scorer=fake_score)
    session = started(deps)
    deps.repo.update_session(
        VISITOR_A, session.session_id, expected_status="in_progress", changes={"turn_count": 30}
    )

    with pytest.raises(ServiceError) as exc:
        send_answer(deps, VISITOR_A, session.session_id, "resposta")

    assert exc.value.code == "session_limit"
    assert deps.repo.list_turns(VISITOR_A, session.session_id)[0].answer_text is None


def test_send_answer_session_limit_by_45_minutes_saves_nothing() -> None:
    deps = make_deps(scorer=fake_score)
    session = started(deps)
    deps.repo.update_session(
        VISITOR_A,
        session.session_id,
        expected_status="in_progress",
        changes={"started_at": T0 - timedelta(hours=1)},
    )

    with pytest.raises(ServiceError) as exc:
        send_answer(deps, VISITOR_A, session.session_id, "resposta")

    assert exc.value.code == "session_limit"
    assert deps.repo.list_turns(VISITOR_A, session.session_id)[0].answer_text is None


def test_send_answer_continues_with_next_public_turn() -> None:
    deps = make_deps(scorer=fake_score)
    session = started(deps)

    result = send_answer(deps, VISITOR_A, session.session_id, "Minha resposta")

    assert result.ended is False
    assert result.turn is not None and result.turn.turn_no == 2
    dumped = result.model_dump_json()
    for private in ("score", "decision", "is_follow_up"):
        assert f'"{private}"' not in dumped
    turns = deps.repo.list_turns(VISITOR_A, session.session_id)
    assert [t.turn_no for t in turns] == [1, 2]
    assert turns[0].answer_text == "Minha resposta" and turns[0].score is not None
    saved = deps.repo.get_session(VISITOR_A, session.session_id)
    assert saved.turn_count == 2 and saved.current_question_id == turns[1].question_id


def test_send_answer_follow_up_keeps_question_and_counts_it() -> None:
    deps = make_deps(scorer=fake_score)
    deps = deps.model_copy(
        update={
            "decider": lambda q, a, s, t: ToolDecision(
                action="follow_up", reason="x", follow_up_text="Pode detalhar?"
            )
        }
    )
    session = started(deps)

    result = send_answer(deps, VISITOR_A, session.session_id, "curta")

    turns = deps.repo.list_turns(VISITOR_A, session.session_id)
    assert result.turn is not None and turns[1].question_id == turns[0].question_id
    assert deps.repo.get_session(VISITOR_A, session.session_id).follow_ups_used == 1


def test_start_and_send_other_visitor_is_not_found() -> None:
    deps = make_deps(scorer=fake_score)
    session = create_session(deps, VISITOR_A, CASE_ID, "text")

    for call in (
        lambda: start_interview(deps, VISITOR_B, session.session_id),
        lambda: send_answer(deps, VISITOR_B, session.session_id, "oi"),
    ):
        with pytest.raises(ServiceError) as exc:
            call()
        assert exc.value.code == "not_found"


def fake_report_result(plan, turns) -> ReportResult:
    report = Report(
        overall_score=4.0,
        competencies=[CompetencyScore(competency="comunicação", score=4.0, summary="ok")],
        strengths=["claro"],
        improvements=[],
    )
    point = SummaryPoint(point="ok", answer_quote="resposta")
    summary = CandidateSummary(
        headline="Boa entrevista",
        summary="Resumo.",
        strengths=[point],
        concerns=[point],
        suggested_next_step="advance",
        next_step_reason="ok",
    )
    return ReportResult(report=report, summary=summary, turns=turns)


def with_report(deps: ServiceDeps, report=fake_report_result) -> tuple[ServiceDeps, Calls]:
    calls = Calls()

    def counted(plan, turns):
        calls.report += 1
        return report(plan, turns)

    return deps.model_copy(update={"report": counted}), calls


def test_end_interview_completes_with_report_saved() -> None:
    deps, calls = with_report(make_deps(scorer=fake_score))
    session = started(deps)

    result = end_interview(deps, VISITOR_A, session.session_id)

    assert result == {"status": "scoring"}
    assert calls.report == 1
    saved = deps.repo.get_session(VISITOR_A, session.session_id)
    assert saved.status == "completed"
    assert saved.overall_score == 4.0 and saved.headline == "Boa entrevista"
    assert saved.competency_scores == {"comunicação": 4.0}
    assert saved.ended_at is not None
    report, summary = deps.reports.load(session.session_id)
    assert report.overall_score == 4.0 and summary.headline == "Boa entrevista"
    assert len(deps.repo.list_turns(VISITOR_A, session.session_id)) == 2  # question + farewell


def test_end_interview_outside_in_progress_is_invalid_state() -> None:
    deps, calls = with_report(make_deps())
    session = create_session(deps, VISITOR_A, CASE_ID, "text")  # ready

    with pytest.raises(ServiceError) as exc:
        end_interview(deps, VISITOR_A, session.session_id)

    assert exc.value.code == "invalid_state"
    assert calls.report == 0


def test_end_interview_other_visitor_is_not_found() -> None:
    deps, _ = with_report(make_deps())
    session = started(deps)

    with pytest.raises(ServiceError) as exc:
        end_interview(deps, VISITOR_B, session.session_id)

    assert exc.value.code == "not_found"


def test_send_answer_last_question_ends_and_generates_report() -> None:
    deps, calls = with_report(make_deps(scorer=fake_score))
    session = started(deps)

    ended = False
    for _ in range(40):
        result = send_answer(deps, VISITOR_A, session.session_id, "resposta")
        if result.ended:
            ended = True
            assert result.turn is None
            break

    assert ended and calls.report == 1
    assert deps.repo.get_session(VISITOR_A, session.session_id).status == "completed"
    assert deps.reports.load(session.session_id)[0].overall_score == 4.0


def test_report_failure_keeps_scoring_with_error_and_turns() -> None:
    def broken(plan, turns):
        raise ReportError("citação inválida")

    deps, _ = with_report(make_deps(scorer=fake_score), broken)
    session = started(deps)

    with pytest.raises(ServiceError) as exc:
        end_interview(deps, VISITOR_A, session.session_id)

    assert exc.value.code == "llm_invalid_output" and exc.value.retryable is True
    saved = deps.repo.get_session(VISITOR_A, session.session_id)
    assert saved.status == "scoring" and saved.error == "citação inválida"
    assert len(deps.repo.list_turns(VISITOR_A, session.session_id)) == 2


def test_get_report_before_completed_is_invalid_state() -> None:
    deps, _ = with_report(make_deps())
    session = started(deps)

    with pytest.raises(ServiceError) as exc:
        get_report(deps, VISITOR_A, session.session_id)

    assert exc.value.code == "invalid_state"


def test_get_report_completed_returns_report_and_full_turns() -> None:
    deps, _ = with_report(make_deps(scorer=fake_score))
    session = started(deps)
    send_answer(deps, VISITOR_A, session.session_id, "resposta")
    end_interview(deps, VISITOR_A, session.session_id)

    view = get_report(deps, VISITOR_A, session.session_id)

    assert view.report.overall_score == 4.0
    assert view.turns[0].score is not None
    assert view.is_above_case_avg is None  # fewer than 3 completed sessions


def test_get_report_other_visitor_is_not_found() -> None:
    deps, _ = with_report(make_deps(scorer=fake_score))
    session = started(deps)
    end_interview(deps, VISITOR_A, session.session_id)

    with pytest.raises(ServiceError) as exc:
        get_report(deps, VISITOR_B, session.session_id)

    assert exc.value.code == "not_found"


def complete_with_score(
    deps: ServiceDeps, visitor: str, score: float, case_id: str = CASE_ID
) -> str:
    """Create a session and mark it completed with a stored report (no model call)."""
    session = create_session(deps, visitor, case_id, "text")
    result = fake_report_result(None, [])
    report = result.report.model_copy(update={"overall_score": score})
    deps.reports.save(session.session_id, report, result.summary)
    deps.repo.update_session(
        visitor,
        session.session_id,
        expected_status="ready",
        changes={
            "status": "completed",
            "overall_score": score,
            "headline": f"nota {score}",
            "ended_at": T0 + timedelta(minutes=int(score * 10)),
        },
    )
    return session.session_id


def test_recruiter_under_three_sessions_shows_all_without_average() -> None:
    deps = make_deps()
    ids = {complete_with_score(deps, VISITOR_A, 2.0), complete_with_score(deps, VISITOR_B, 4.0)}

    result = list_recruiter_candidates(deps, CASE_ID)

    assert [s.case_id for s in result.stats] == [CASE_ID]
    assert result.stats[0].completed_sessions == 2
    assert result.stats[0].average_score is None
    assert {c.session_id for c in result.candidates} == ids
    assert all(c.delta_vs_case_avg is None for c in result.candidates)


def test_recruiter_with_average_shows_only_above_average() -> None:
    deps = make_deps()
    complete_with_score(deps, VISITOR_A, 2.0)
    complete_with_score(deps, VISITOR_A, 3.0)
    top = complete_with_score(deps, VISITOR_B, 4.0)

    result = list_recruiter_candidates(deps)

    stats = {s.case_id: s for s in result.stats}
    assert len(stats) == 5  # one per case, even without sessions
    assert stats[CASE_ID].average_score == 3.0
    assert [c.session_id for c in result.candidates] == [top]
    assert result.candidates[0].delta_vs_case_avg == 1.0
    assert result.candidates[0].candidate_no == 3


def test_recruiter_orders_by_delta_then_most_recent() -> None:
    deps = make_deps()
    for score in (1.0, 1.0, 1.0):
        complete_with_score(deps, VISITOR_A, score)
    best = complete_with_score(deps, VISITOR_B, 5.0)
    mid = complete_with_score(deps, VISITOR_B, 3.0)

    result = list_recruiter_candidates(deps, CASE_ID)

    assert [c.session_id for c in result.candidates] == [best, mid]


def test_recruiter_responses_never_expose_visitor_id() -> None:
    deps = make_deps()
    session_id = complete_with_score(deps, VISITOR_A, 4.0)

    listing = list_recruiter_candidates(deps).model_dump_json()
    detail = get_recruiter_candidate(deps, session_id).model_dump_json()

    for payload in (listing, detail):
        assert "visitor_id" not in payload
        assert VISITOR_A not in payload


def test_recruiter_detail_returns_row_summary_report_and_turns() -> None:
    deps = make_deps()
    session_id = complete_with_score(deps, VISITOR_A, 4.0)

    detail = get_recruiter_candidate(deps, session_id)

    assert detail.row.session_id == session_id
    assert detail.row.headline == "nota 4.0"
    assert detail.summary.headline == "Boa entrevista"
    assert detail.report.overall_score == 4.0
    assert detail.turns == []


def test_recruiter_detail_not_completed_or_missing_is_not_found() -> None:
    deps = make_deps()
    session = create_session(deps, VISITOR_A, CASE_ID, "text")

    for session_id in (session.session_id, "nope"):
        with pytest.raises(ServiceError) as exc:
            get_recruiter_candidate(deps, session_id)
        assert exc.value.code == "not_found"


def test_recruiter_hides_deleted_session() -> None:
    deps = make_deps()
    session_id = complete_with_score(deps, VISITOR_A, 4.0)
    delete_session(deps, VISITOR_A, session_id)

    assert list_recruiter_candidates(deps).candidates == []
    with pytest.raises(ServiceError):
        get_recruiter_candidate(deps, session_id)


def test_get_report_is_above_case_avg_with_three_sessions() -> None:
    deps = make_deps()
    complete_with_score(deps, VISITOR_A, 2.0)
    low = complete_with_score(deps, VISITOR_A, 3.0)
    high = complete_with_score(deps, VISITOR_B, 4.0)

    assert get_report(deps, VISITOR_B, high).is_above_case_avg is True
    assert get_report(deps, VISITOR_A, low).is_above_case_avg is False
