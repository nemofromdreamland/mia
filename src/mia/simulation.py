"""Simulation orchestration: session lifecycle rules, with no terminal I/O.

The CLI (and later the API) calls these functions; every model call is injected
through `SimulationDeps`, so the whole flow can be tested with fakes.
"""

import secrets
from collections.abc import Callable
from typing import Final

from pydantic import BaseModel, ConfigDict

from mia.interviewer import Clock, Decider, InterviewState, Scorer, Writer, start
from mia.llm import LLMInvalidOutputError
from mia.prep_graph import PrepError, PrepInput, PrepResult
from mia.report_graph import ReportResult
from mia.repositories import SessionRepository
from mia.schemas import InterviewPlan, Session, Turn

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
