"""Interviewer: deterministic state machine for the interview loop.

The code decides the rules (time, turn and follow-up limits, which plan question
comes next); the LLM only suggests whether to dig deeper and writes the speech.
External decisions (LLM, judge, clock) are injected as callables.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from mia.schemas import InterviewPlan, Phase, Question, Turn

EndReason = Literal["plan_done", "time_or_turns", "visitor"]

Writer = Callable[[Phase, str, str, list[Turn]], str]  # phase, question, instruction, history
Clock = Callable[[], datetime]

ASK_INSTRUCTION = (
    "Faça a pergunta abaixo ao candidato, com uma frase curta de transição se fizer sentido."
)


class InterviewError(Exception):
    """Invalid operation on the interview (ended, empty or too long answer)."""


class InterviewLimits(BaseModel):
    max_turns: int = 30
    max_follow_ups: int = 2
    max_answer_chars: int = 4000
    hard_max_minutes: int = 15
    slack_minutes: int = 3
    history_turns: int = 6


class InterviewState(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: str
    plan: InterviewPlan
    current_index: int
    follow_ups_used: int
    turn_count: int
    started_at: datetime
    turns: list[Turn]
    ended: bool = False
    end_reason: EndReason | None = None


class TimeStatus(BaseModel):
    over: bool
    minutes_left: float


def current_question(state: InterviewState) -> Question:
    return state.plan.questions[state.current_index]


def next_question(state: InterviewState) -> Question | None:
    """Next question in plan order, or None when the current one is the last."""
    index = state.current_index + 1
    return state.plan.questions[index] if index < len(state.plan.questions) else None


def max_minutes(plan: InterviewPlan, limits: InterviewLimits) -> int:
    return min(plan.estimated_minutes + limits.slack_minutes, limits.hard_max_minutes)


def time_check(state: InterviewState, now: datetime, limits: InterviewLimits) -> TimeStatus:
    """Over when the turn limit or the time limit is reached; minutes_left never negative."""
    elapsed = (now - state.started_at).total_seconds() / 60
    minutes_left = max(0.0, max_minutes(state.plan, limits) - elapsed)
    over = state.turn_count >= limits.max_turns or minutes_left <= 0
    return TimeStatus(over=over, minutes_left=minutes_left)


def start(
    session_id: str, plan: InterviewPlan, *, writer: Writer, clock: Clock
) -> tuple[InterviewState, Turn]:
    """Open the interview on the first plan question; returns the state and the first turn."""
    question = plan.questions[0]
    now = clock()
    turn = Turn(
        session_id=session_id,
        turn_no=1,
        question_id=question.id,
        interviewer_text=writer(question.phase, question.text, ASK_INSTRUCTION, []),
        created_at=now,
    )
    state = InterviewState(
        session_id=session_id,
        plan=plan,
        current_index=0,
        follow_ups_used=0,
        turn_count=1,
        started_at=now,
        turns=[turn],
    )
    return state, turn
