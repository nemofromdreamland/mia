"""Interviewer: deterministic state machine for the interview loop.

The code decides the rules (time, turn and follow-up limits, which plan question
comes next); the LLM only suggests whether to dig deeper and writes the speech.
External decisions (LLM, judge, clock) are injected as callables.
"""

import re
from collections.abc import Callable
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from mia.pii import mask_text
from mia.prompts import load_prompt, run_prompt, run_prompt_structured
from mia.schemas import (
    AnswerScore,
    InterviewPlan,
    Persona,
    Phase,
    Question,
    ToolDecision,
    Turn,
)

EndReason = Literal["plan_done", "time_or_turns", "visitor"]

Writer = Callable[[Phase, str, str, list[Turn]], str]  # phase, question, instruction, history
Clock = Callable[[], datetime]
Scorer = Callable[[Question, str], AnswerScore]

ASK_INSTRUCTION = (
    "Faça a pergunta abaixo ao candidato, com uma frase curta de transição se fizer sentido."
)
FOLLOW_UP_INSTRUCTION = "Aprofunde a resposta anterior fazendo a pergunta abaixo, sem avaliar."
CLOSING_INSTRUCTION = "Encerre a entrevista agradecendo ao candidato, sem avaliar nem dar feedback."
CLOSING_TEXT = "Agradeça a participação e informe que a entrevista terminou."


class InterviewError(Exception):
    """Invalid operation on the interview (ended, empty or too long answer)."""


class InterviewLimits(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_turns: int = 30
    max_follow_ups: int = 2
    max_questions: int = 3  # used by shorten_plan (web only)
    target_minutes: int = 6  # used by shorten_plan (web only)
    max_answer_chars: int = 4000
    hard_max_minutes: int = 15
    slack_minutes: int = 3
    history_turns: int = 6


DEFAULT_LIMITS = InterviewLimits()
# Web demo (spec 4.7c): ~6 min, 3 questions, 1 follow-up. CLI and evals keep DEFAULT_LIMITS.
WEB_LIMITS = InterviewLimits(max_follow_ups=1, hard_max_minutes=8)

SHORT_PLAN_PHASES = ("opening", "technical", "behavioral")


def shorten_plan(plan: InterviewPlan, limits: InterviewLimits = WEB_LIMITS) -> InterviewPlan:
    """Keep `max_questions`: first opening, first technical, first behavioral question; a
    missing phase is filled with the next questions in plan order (spec 4.7c, R4)."""
    chosen: list[str] = []
    for phase in SHORT_PLAN_PHASES:
        first = next(
            (q.id for q in plan.questions if q.phase == phase and q.id not in chosen), None
        )
        if first is not None:
            chosen.append(first)
    for question in plan.questions:
        if len(chosen) >= limits.max_questions:
            break
        if question.id not in chosen:
            chosen.append(question.id)
    keep = set(chosen[: limits.max_questions])
    return plan.model_copy(
        update={
            "questions": [q for q in plan.questions if q.id in keep],
            "estimated_minutes": min(plan.estimated_minutes, limits.target_minutes),
        }
    )


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


Decider = Callable[[Question, str, InterviewState, TimeStatus], ToolDecision]


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


class StepResult(BaseModel):
    state: InterviewState
    answered: Turn  # the answered turn, with decision and score
    next_turn: Turn  # next speech: follow-up, next question or closing


def _validate_answer(state: InterviewState, text: str, limits: InterviewLimits) -> None:
    if state.ended:
        raise InterviewError("the interview has already ended")
    if not text.strip():
        raise InterviewError("the answer is empty")
    if len(text) > limits.max_answer_chars:
        raise InterviewError(f"the answer exceeds {limits.max_answer_chars} characters")


def _wants_follow_up(
    decision: ToolDecision, state: InterviewState, limits: InterviewLimits
) -> bool:
    """The LLM only suggests: a follow-up needs text and a free slot (the code decides)."""
    has_text = bool(decision.follow_up_text and decision.follow_up_text.strip())
    return (
        decision.action == "follow_up"
        and has_text
        and state.follow_ups_used < limits.max_follow_ups
    )


def _history(turns: list[Turn], limits: InterviewLimits) -> list[Turn]:
    return turns[-limits.history_turns :]


def _history_text(turns: list[Turn]) -> str:
    """Plain-text history (answers are already masked); empty when there is none."""
    lines: list[str] = []
    for turn in turns:
        lines.append(f"Entrevistador: {turn.interviewer_text}")
        if turn.answer_text:
            lines.append(f"Candidato: {turn.answer_text}")
    return "\n".join(lines)


def should_follow_up(
    question: Question,
    answer: str,
    state: InterviewState,
    status: TimeStatus,
    *,
    limits: InterviewLimits = DEFAULT_LIMITS,
    params: dict[str, Any] | None = None,
    **llm_options: Any,
) -> ToolDecision:
    """Ask the fast LLM (prompt follow_up) whether to dig deeper; `answer` must be masked."""
    variables = {
        "question": question.text,
        "look_for": "; ".join(question.look_for),
        "follow_ups_left": str(max(0, limits.max_follow_ups - state.follow_ups_used)),
        "minutes_left": f"{status.minutes_left:.1f}",
        "history": _history_text(_history(state.turns, limits)),
        "answer": answer,
    }
    return run_prompt_structured(
        load_prompt("follow_up", 1),
        variables,
        ToolDecision,
        session_id=state.session_id,
        params=params,
        **llm_options,
    )


def default_writer(*, persona: Persona, **llm_options: Any) -> Writer:
    """Writer backed by the interviewer prompt v4 (short acknowledgement of the last answer);
    the code supplies phase and question."""
    prompt = load_prompt("interviewer", 4)

    def write(phase: Phase, question: str, instruction: str, history: list[Turn]) -> str:
        variables = {
            "persona": persona,
            "phase": phase,
            "question": question,
            "instruction": instruction,
            "history": _history_text(history),
        }
        return finish_at_sentence(run_prompt(prompt, variables, **llm_options))

    return write


SENTENCE_END = re.compile(r"[.?!…]")


def finish_at_sentence(text: str) -> str:
    """Never show a line cut by max_tokens: drop the unfinished tail after the last sentence end.

    A text with no sentence end at all is returned as it came (spec 4.7c, R2).
    """
    text = text.strip()
    ends = [match.end() for match in SENTENCE_END.finditer(text)]
    if not ends or ends[-1] == len(text):
        return text
    return text[: ends[-1]]


def score_answer(scorer: Scorer, question: Question, answer: str) -> AnswerScore | None:
    """Run the judge; a failure must never block the interview, so it yields None."""
    try:
        return scorer(question, answer)
    except Exception:  # noqa: BLE001 - the judge is best-effort by design (R12)
        return None


def end_interview(
    state: InterviewState,
    reason: EndReason,
    *,
    writer: Writer,
    clock: Clock,
    limits: InterviewLimits = DEFAULT_LIMITS,
) -> tuple[InterviewState, Turn]:
    """Close the interview with a farewell turn; returns the ended state and that turn."""
    if state.ended:
        raise InterviewError("the interview has already ended")
    question = current_question(state)
    turn = Turn(
        session_id=state.session_id,
        turn_no=state.turn_count + 1,
        question_id=question.id,
        interviewer_text=writer(
            "closing", CLOSING_TEXT, CLOSING_INSTRUCTION, _history(state.turns, limits)
        ),
        created_at=clock(),
    )
    ended = state.model_copy(
        update={
            "turn_count": state.turn_count + 1,
            "turns": [*state.turns, turn],
            "ended": True,
            "end_reason": reason,
        }
    )
    return ended, turn


def answer(
    state: InterviewState,
    text: str,
    *,
    decider: Decider,
    writer: Writer,
    scorer: Scorer,
    clock: Clock,
    limits: InterviewLimits = DEFAULT_LIMITS,
) -> StepResult:
    """Apply the candidate's answer and return the new state, the answered turn and the next one."""
    _validate_answer(state, text, limits)
    masked = mask_text(text)
    now = clock()
    question = current_question(state)
    status = time_check(state, now, limits)
    decision = None if status.over else decider(question, masked, state, status)

    answered = state.turns[-1].model_copy(
        update={
            "answer_text": masked,
            "decision": decision,
            "score": score_answer(scorer, question, masked),
        }
    )
    base = state.model_copy(update={"turns": [*state.turns[:-1], answered]})

    if status.over:
        return _close(base, answered, "time_or_turns", writer, clock, limits)
    assert decision is not None
    if _wants_follow_up(decision, state, limits):
        assert decision.follow_up_text is not None
        return _step(
            base, answered, question.phase, decision.follow_up_text, True, writer, now, limits
        )
    upcoming = next_question(state)
    if upcoming is None:
        return _close(base, answered, "plan_done", writer, clock, limits)
    return _step(base, answered, upcoming.phase, upcoming.text, False, writer, now, limits)


def _close(
    base: InterviewState,
    answered: Turn,
    reason: EndReason,
    writer: Writer,
    clock: Clock,
    limits: InterviewLimits,
) -> StepResult:
    ended, turn = end_interview(base, reason, writer=writer, clock=clock, limits=limits)
    return StepResult(state=ended, answered=answered, next_turn=turn)


def _step(
    base: InterviewState,
    answered: Turn,
    phase: Phase,
    text: str,
    is_follow_up: bool,
    writer: Writer,
    now: datetime,
    limits: InterviewLimits,
) -> StepResult:
    """Ask a follow-up (same question) or the next plan question."""
    index = base.current_index if is_follow_up else base.current_index + 1
    follow_ups = base.follow_ups_used + 1 if is_follow_up else 0
    instruction = FOLLOW_UP_INSTRUCTION if is_follow_up else ASK_INSTRUCTION
    next_turn = Turn(
        session_id=base.session_id,
        turn_no=base.turn_count + 1,
        question_id=base.plan.questions[index].id,
        interviewer_text=writer(phase, text, instruction, _history(base.turns, limits)),
        is_follow_up=is_follow_up,
        created_at=now,
    )
    new_state = base.model_copy(
        update={
            "current_index": index,
            "follow_ups_used": follow_ups,
            "turn_count": base.turn_count + 1,
            "turns": [*base.turns, next_turn],
        }
    )
    return StepResult(state=new_state, answered=answered, next_turn=next_turn)
