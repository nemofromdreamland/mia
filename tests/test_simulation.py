"""Tests for the simulation orchestration (no real model: every dependency is a fake)."""

import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from mia.interviewer import InterviewError
from mia.llm import LLMInvalidOutputError
from mia.prep_graph import PrepInput, PrepResult, PrepValidationError
from mia.report_graph import ReportResult, ReportValidationError
from mia.repositories import InMemorySessionRepository
from mia.schemas import (
    AnswerScore,
    CandidateSummary,
    InterviewPlan,
    Phase,
    Report,
    Screening,
    ToolDecision,
    Turn,
)
from mia.simulation import (
    LOCAL_VISITOR,
    SimulationDeps,
    SimulationError,
    begin,
    default_deps,
    finish,
    new_session_id,
    prepare,
    reply,
    stop,
)

FIXTURES = Path(__file__).parent / "fixtures" / "prep"
REPORT_FIXTURES = Path(__file__).parent / "fixtures" / "report"
T0 = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")


def clock() -> datetime:
    return T0


def fake_writer(phase: Phase, question: str, instruction: str, history: list[Turn]) -> str:
    return f"[{phase}] {question}"


def fake_decider(question, answer, state, time_status) -> ToolDecision:
    return ToolDecision(action="next_question", reason="ok")


def fake_scorer(question, answer):
    raise AssertionError("the scorer is not used in this step")


def prep_input() -> PrepInput:
    return PrepInput(
        cv_path=FIXTURES / "cv_ficticio.md",
        job_text="Vaga fictícia",
        persona="technical",
        level="junior",
        estimated_minutes=20,
        language="pt-BR",
    )


def fixture_result() -> PrepResult:
    return PrepResult(
        screening=Screening.model_validate_json(
            (FIXTURES / "screening_ok.json").read_text(encoding="utf-8")
        ),
        plan=InterviewPlan.model_validate_json(
            (FIXTURES / "plan_ok.json").read_text(encoding="utf-8")
        ),
    )


def make_deps(prep=None) -> SimulationDeps:
    return SimulationDeps(
        repo=InMemorySessionRepository(clock=clock),
        decider=fake_decider,
        writer=fake_writer,
        scorer=fake_scorer,
        clock=clock,
        prep=prep or (lambda data: fixture_result()),
        report=lambda plan, turns: pytest.fail("report is not used in this step"),
    )


def test_new_session_id_is_a_valid_ulid() -> None:
    session_id = new_session_id(clock)
    assert ULID_RE.match(session_id)


def test_new_session_ids_are_unique() -> None:
    assert len({new_session_id(clock) for _ in range(50)}) == 50


def test_new_session_ids_sort_by_time() -> None:
    early = new_session_id(lambda: datetime(2026, 1, 1, tzinfo=UTC))
    late = new_session_id(lambda: datetime(2026, 12, 1, tzinfo=UTC))
    assert early < late


def test_prepare_ok_marks_session_ready() -> None:
    deps = make_deps()

    session, result = prepare(deps, prep_input())

    stored = deps.repo.get_session(LOCAL_VISITOR, session.session_id)
    assert stored.status == "ready"
    assert stored.fit_score == result.screening.fit_score
    assert stored.visitor_id == "local"
    assert stored.case_id is None
    assert stored.mode == "text"
    assert stored.persona == "technical"
    assert stored.language == "pt-BR"
    assert stored.job_title is None
    assert session == stored


def test_prepare_creates_the_session_as_preparing_before_calling_prep() -> None:
    seen: list[str] = []
    deps = make_deps()

    def prep(data: PrepInput) -> PrepResult:
        (only,) = deps.repo._sessions.values()  # type: ignore[attr-defined]
        seen.append(only.status)
        return fixture_result()

    deps = deps.model_copy(update={"prep": prep})
    prepare(deps, prep_input())

    assert seen == ["preparing"]


@pytest.mark.parametrize(
    "error",
    [PrepValidationError(["x"]), LLMInvalidOutputError("bad json")],
)
def test_prepare_failure_marks_session_failed(error: Exception) -> None:
    def prep(data: PrepInput) -> PrepResult:
        raise error

    deps = make_deps(prep)

    with pytest.raises(SimulationError) as info:
        prepare(deps, prep_input())

    (session,) = deps.repo._sessions.values()  # type: ignore[attr-defined]
    assert session.status == "failed"
    assert session.error
    assert str(info.value) == session.error


def test_begin_starts_the_interview_and_saves_first_turn() -> None:
    deps = make_deps()
    session, result = prepare(deps, prep_input())

    state, turn = begin(deps, session, result.plan)

    stored = deps.repo.get_session(LOCAL_VISITOR, session.session_id)
    assert stored.status == "in_progress"
    assert stored.started_at == T0
    assert stored.current_question_id == result.plan.questions[0].id
    assert stored.turn_count == 1
    assert deps.repo.list_turns(LOCAL_VISITOR, session.session_id) == [turn]
    assert state.session_id == session.session_id
    assert turn.turn_no == 1
    assert turn.interviewer_text.startswith("[")


# ---------- step 3: reply, stop, finish, default_deps ----------


def fixture_report(turns: list[Turn]) -> ReportResult:
    score = AnswerScore(
        score=4, criteria_met=[], evidence_quotes=[], justification="ok", quotes_verified=True
    )
    return ReportResult(
        report=Report.model_validate_json(
            (REPORT_FIXTURES / "report_ok.json").read_text(encoding="utf-8")
        ),
        summary=CandidateSummary.model_validate_json(
            (REPORT_FIXTURES / "summary_ok.json").read_text(encoding="utf-8")
        ),
        turns=[t.model_copy(update={"score": score}) if t.answer_text else t for t in turns],
    )


def started(report=None):
    deps = make_deps()
    if report is not None:
        deps = deps.model_copy(update={"report": report})
    session, result = prepare(deps, prep_input())
    state, _ = begin(deps, session, result.plan)
    return deps, session, state


def test_reply_saves_answered_turn_and_next_turn() -> None:
    deps, session, state = started()

    step = reply(deps, state, "Minha resposta, escreva para a@b.com")

    turns = deps.repo.list_turns(LOCAL_VISITOR, session.session_id)
    assert [t.turn_no for t in turns] == [1, 2]
    assert turns[0].answer_text is not None
    assert "a@b.com" not in turns[0].answer_text
    assert turns[0] == step.answered
    assert turns[1] == step.next_turn
    stored = deps.repo.get_session(LOCAL_VISITOR, session.session_id)
    assert stored.turn_count == 2
    assert stored.current_question_id == step.next_turn.question_id
    assert stored.follow_ups_used == step.state.follow_ups_used
    assert stored.status == "in_progress"


def test_reply_empty_answer_raises_and_saves_nothing() -> None:
    deps, session, state = started()

    with pytest.raises(InterviewError):
        reply(deps, state, "   ")

    assert len(deps.repo.list_turns(LOCAL_VISITOR, session.session_id)) == 1
    assert deps.repo.get_session(LOCAL_VISITOR, session.session_id).turn_count == 1


def test_reply_through_the_whole_plan_ends_with_closing_turn() -> None:
    deps, session, state = started()

    while not state.ended:
        state = reply(deps, state, "resposta").state

    assert state.end_reason == "plan_done"
    turns = deps.repo.list_turns(LOCAL_VISITOR, session.session_id)
    assert turns[-1].interviewer_text.startswith("[closing]")
    assert len(turns) == state.turn_count


def test_stop_saves_closing_turn_with_visitor_reason() -> None:
    deps, session, state = started()
    state = reply(deps, state, "resposta").state

    ended, closing = stop(deps, state)

    assert ended.ended
    assert ended.end_reason == "visitor"
    turns = deps.repo.list_turns(LOCAL_VISITOR, session.session_id)
    assert turns[-1] == closing
    assert closing.interviewer_text.startswith("[closing]")
    stored = deps.repo.get_session(LOCAL_VISITOR, session.session_id)
    assert stored.turn_count == ended.turn_count


def test_finish_completes_the_session_with_the_report() -> None:
    received: list[list[Turn]] = []

    def report(plan, turns):
        received.append(turns)
        return fixture_report(turns)

    deps, session, state = started(report)
    state = reply(deps, state, "resposta").state
    state, _ = stop(deps, state)
    before = deps.repo.list_turns(LOCAL_VISITOR, session.session_id)

    result = finish(deps, state)

    stored = deps.repo.get_session(LOCAL_VISITOR, session.session_id)
    assert stored.status == "completed"
    assert stored.ended_at == T0
    assert stored.overall_score == result.report.overall_score
    assert stored.headline == result.summary.headline
    assert stored.competency_scores == {c.competency: c.score for c in result.report.competencies}
    assert received == [before]
    saved = deps.repo.list_turns(LOCAL_VISITOR, session.session_id)
    assert saved[0].score is not None  # the scored turn came back from the report


@pytest.mark.parametrize(
    "error",
    [ReportValidationError(["x"]), LLMInvalidOutputError("bad json")],
)
def test_finish_failure_marks_session_failed(error: Exception) -> None:
    def report(plan, turns):
        raise error

    deps, session, state = started(report)
    state, _ = stop(deps, state)

    with pytest.raises(SimulationError) as info:
        finish(deps, state)

    stored = deps.repo.get_session(LOCAL_VISITOR, session.session_id)
    assert stored.status == "failed"
    assert stored.error == str(info.value)


def test_default_deps_wires_the_real_pieces_with_an_in_memory_repo() -> None:
    deps = default_deps("technical")

    assert isinstance(deps.repo, InMemorySessionRepository)
    assert callable(deps.decider)
    assert callable(deps.writer)
    assert callable(deps.report)
    repo = InMemorySessionRepository()
    assert default_deps("hr", repo).repo is repo
