"""Tests for the simulation orchestration (no real model: every dependency is a fake)."""

import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from mia.llm import LLMInvalidOutputError
from mia.prep_graph import PrepInput, PrepResult, PrepValidationError
from mia.repositories import InMemorySessionRepository
from mia.schemas import InterviewPlan, Phase, Screening, ToolDecision, Turn
from mia.simulation import (
    LOCAL_VISITOR,
    SimulationDeps,
    SimulationError,
    begin,
    new_session_id,
    prepare,
)

FIXTURES = Path(__file__).parent / "fixtures" / "prep"
T0 = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")


def clock() -> datetime:
    return T0


def fake_writer(phase: Phase, question: str, instruction: str, history: list[Turn]) -> str:
    return f"[{phase}] {question}"


def fake_decider(question, answer, state, time_status) -> ToolDecision:
    return ToolDecision(action="next", reason="ok")


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
