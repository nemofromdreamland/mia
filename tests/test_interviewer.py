"""Tests for the interviewer state machine (no real LLM: writer and clock are fakes)."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from mia.interviewer import (
    InterviewLimits,
    InterviewState,
    next_question,
    start,
    time_check,
)
from mia.schemas import InterviewPlan, Phase, Turn

PLAN_PATH = Path(__file__).parent / "fixtures" / "prep" / "plan_ok.json"
T0 = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)


@pytest.fixture
def plan() -> InterviewPlan:
    return InterviewPlan.model_validate(json.loads(PLAN_PATH.read_text(encoding="utf-8")))


def fake_writer(phase: Phase, question: str, instruction: str, history: list[Turn]) -> str:
    return f"[{phase}] {question}"


def clock_at(moment: datetime):
    return lambda: moment


def started(plan: InterviewPlan) -> InterviewState:
    state, _ = start("s1", plan, writer=fake_writer, clock=clock_at(T0))
    return state


# --- start ------------------------------------------------------------------


def test_start_sets_first_question(plan: InterviewPlan) -> None:
    state, turn = start("s1", plan, writer=fake_writer, clock=clock_at(T0))
    assert state.current_index == 0
    assert state.follow_ups_used == 0
    assert state.turn_count == 1
    assert state.started_at == T0
    assert state.ended is False
    assert state.end_reason is None
    assert state.turns == [turn]
    assert turn.turn_no == 1
    assert turn.question_id == "q1"
    assert turn.session_id == "s1"
    assert turn.is_follow_up is False
    assert turn.answer_text is None
    assert turn.interviewer_text == f"[opening] {plan.questions[0].text}"
    assert turn.created_at == T0


def test_state_is_frozen(plan: InterviewPlan) -> None:
    state = started(plan)
    with pytest.raises(ValidationError):
        state.turn_count = 5  # type: ignore[misc]


# --- next_question ----------------------------------------------------------


def test_next_question_returns_following_question(plan: InterviewPlan) -> None:
    question = next_question(started(plan))
    assert question is not None
    assert question.id == "q2"


def test_next_question_none_on_last(plan: InterviewPlan) -> None:
    state = started(plan).model_copy(update={"current_index": len(plan.questions) - 1})
    assert next_question(state) is None


# --- time_check -------------------------------------------------------------


def test_time_limit_is_estimate_plus_slack_capped(plan: InterviewPlan) -> None:
    # fixture plan estimates 20 min -> min(20 + 3, 15) = 15
    state = started(plan)
    limits = InterviewLimits()
    assert time_check(state, T0 + timedelta(minutes=14), limits).over is False
    assert time_check(state, T0 + timedelta(minutes=15), limits).over is True


def test_short_plan_uses_estimate_plus_slack(plan: InterviewPlan) -> None:
    short = plan.model_copy(update={"estimated_minutes": 10})
    state = started(short)
    limits = InterviewLimits()
    status = time_check(state, T0 + timedelta(minutes=12), limits)
    assert status.over is False
    assert status.minutes_left == pytest.approx(1.0)
    assert time_check(state, T0 + timedelta(minutes=13), limits).over is True


def test_minutes_left_never_negative(plan: InterviewPlan) -> None:
    status = time_check(started(plan), T0 + timedelta(minutes=20), InterviewLimits())
    assert status.over is True
    assert status.minutes_left == 0


def test_turn_limit_ends(plan: InterviewPlan) -> None:
    state = started(plan).model_copy(update={"turn_count": 30})
    assert time_check(state, T0, InterviewLimits()).over is True
    state = state.model_copy(update={"turn_count": 29})
    assert time_check(state, T0, InterviewLimits()).over is False
