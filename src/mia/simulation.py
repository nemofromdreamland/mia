"""Simulation orchestration: session lifecycle rules, with no terminal I/O.

The CLI (and later the API) calls these functions; every model call is injected
through `SimulationDeps`, so the whole flow can be tested with fakes.
"""

import secrets
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Final

from pydantic import BaseModel, ConfigDict

from mia.interviewer import (
    Clock,
    Decider,
    InterviewState,
    Scorer,
    StepResult,
    Writer,
    answer,
    default_writer,
    end_interview,
    should_follow_up,
    start,
)
from mia.judge import default_scorer
from mia.llm import LLMInvalidOutputError
from mia.prep_graph import PrepError, PrepInput, PrepResult, run_prep
from mia.report_graph import ReportError, ReportResult, run_report
from mia.repositories import InMemorySessionRepository, SessionRepository
from mia.schemas import InterviewPlan, Persona, Session, Turn

LOCAL_VISITOR: Final = "local"
_CROCKFORD: Final = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


class SimulationError(Exception):
    """Short message meant for the user (stderr + exit code 1)."""


class SimulationDeps(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    repo: SessionRepository
    decider: Decider
    writer: Writer
    scorer: Scorer
    clock: Clock
    prep: Callable[[PrepInput], PrepResult]
    report: Callable[[InterviewPlan, list[Turn]], ReportResult]


def new_session_id(clock: Clock) -> str:
    """ULID: 48 bits of time (ms) + 80 random bits, as 26 Crockford base32 characters."""
    millis = int(clock().timestamp() * 1000)
    value = (millis << 80) | int.from_bytes(secrets.token_bytes(10), "big")
    chars = [_CROCKFORD[(value >> shift) & 31] for shift in range(125, -1, -5)]
    return "".join(chars)


def prepare(deps: SimulationDeps, data: PrepInput) -> tuple[Session, PrepResult]:
    """Create the session as `preparing`, run the prep and mark it `ready` (or `failed`)."""
    now = deps.clock()
    session = Session(
        visitor_id=LOCAL_VISITOR,
        session_id=new_session_id(deps.clock),
        case_id=None,
        status="preparing",
        persona=data.persona,
        language=data.language,
        mode="text",
        created_at=now,
        updated_at=now,
    )
    deps.repo.create_session(session)
    try:
        result = deps.prep(data)
    except (PrepError, LLMInvalidOutputError) as exc:
        message = str(exc) or type(exc).__name__
        deps.repo.update_session(
            LOCAL_VISITOR,
            session.session_id,
            expected_status="preparing",
            changes={"status": "failed", "error": message},
        )
        raise SimulationError(message) from exc
    ready = deps.repo.update_session(
        LOCAL_VISITOR,
        session.session_id,
        expected_status="preparing",
        changes={"status": "ready", "fit_score": result.screening.fit_score},
    )
    return ready, result


def begin(
    deps: SimulationDeps, session: Session, plan: InterviewPlan
) -> tuple[InterviewState, Turn]:
    """Open the interview: save the first turn and mark the session `in_progress`."""
    state, turn = start(session.session_id, plan, writer=deps.writer, clock=deps.clock)
    deps.repo.put_turn(LOCAL_VISITOR, turn)
    deps.repo.update_session(
        LOCAL_VISITOR,
        session.session_id,
        expected_status="ready",
        changes={
            "status": "in_progress",
            "started_at": state.started_at,
            "current_question_id": turn.question_id,
            "follow_ups_used": state.follow_ups_used,
            "turn_count": state.turn_count,
        },
    )
    return state, turn


def _save_progress(deps: SimulationDeps, state: InterviewState, turns: list[Turn]) -> None:
    """Persist the given turns and the counters kept in the session row."""
    for turn in turns:
        deps.repo.put_turn(LOCAL_VISITOR, turn)
    deps.repo.update_session(
        LOCAL_VISITOR,
        state.session_id,
        expected_status="in_progress",
        changes={
            "current_question_id": turns[-1].question_id,
            "follow_ups_used": state.follow_ups_used,
            "turn_count": state.turn_count,
        },
    )


def reply(deps: SimulationDeps, state: InterviewState, text: str) -> StepResult:
    """Apply an answer; `InterviewError` (empty, too long, ended) propagates and saves nothing."""
    step = answer(
        state,
        text,
        decider=deps.decider,
        writer=deps.writer,
        scorer=deps.scorer,
        clock=deps.clock,
    )
    _save_progress(deps, step.state, [step.answered, step.next_turn])
    return step


def stop(deps: SimulationDeps, state: InterviewState) -> tuple[InterviewState, Turn]:
    """The visitor ends the interview: save the closing turn."""
    ended, turn = end_interview(state, "visitor", writer=deps.writer, clock=deps.clock)
    _save_progress(deps, ended, [turn])
    return ended, turn


def finish(deps: SimulationDeps, state: InterviewState) -> ReportResult:
    """Score the finished interview and complete the session (or mark it `failed`)."""
    session_id = state.session_id
    deps.repo.update_session(
        LOCAL_VISITOR,
        session_id,
        expected_status="in_progress",
        changes={"status": "scoring", "ended_at": deps.clock()},
    )
    try:
        result = deps.report(state.plan, deps.repo.list_turns(LOCAL_VISITOR, session_id))
    except (ReportError, LLMInvalidOutputError) as exc:
        message = str(exc) or type(exc).__name__
        deps.repo.update_session(
            LOCAL_VISITOR,
            session_id,
            expected_status="scoring",
            changes={"status": "failed", "error": message},
        )
        raise SimulationError(message) from exc
    for turn in result.turns:
        deps.repo.put_turn(LOCAL_VISITOR, turn)
    deps.repo.update_session(
        LOCAL_VISITOR,
        session_id,
        expected_status="scoring",
        changes={
            "status": "completed",
            "overall_score": result.report.overall_score,
            "competency_scores": {c.competency: c.score for c in result.report.competencies},
            "headline": result.summary.headline,
        },
    )
    return result


def _utc_now() -> datetime:
    return datetime.now(UTC)


def default_deps(persona: Persona, repo: SessionRepository | None = None) -> SimulationDeps:
    """Real wiring: the models behind the decider, writer, judge, prep and report."""
    scorer = default_scorer()
    return SimulationDeps(
        repo=repo or InMemorySessionRepository(),
        decider=should_follow_up,
        writer=default_writer(persona=persona),
        scorer=scorer,
        clock=_utc_now,
        prep=run_prep,
        report=lambda plan, turns: run_report(plan, turns, scorer=scorer),
    )
