"""Tests for the interviewer state machine (no real LLM: writer and clock are fakes)."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from pydantic import ValidationError

from mia.interviewer import (
    InterviewError,
    InterviewLimits,
    InterviewState,
    StepResult,
    TimeStatus,
    answer,
    default_writer,
    end_interview,
    next_question,
    score_answer,
    should_follow_up,
    start,
    time_check,
)
from mia.schemas import AnswerScore, InterviewPlan, Phase, Question, ToolDecision, Turn

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


# --- answer: validation, masking, follow-up vs next question -----------------


class FakeDecider:
    """Returns the queued decisions in order and records what it received."""

    def __init__(self, *decisions: ToolDecision) -> None:
        self.decisions = list(decisions)
        self.calls: list[tuple[Question, str, TimeStatus]] = []

    def __call__(
        self, question: Question, answer: str, state: InterviewState, status: TimeStatus
    ) -> ToolDecision:
        self.calls.append((question, answer, status))
        return self.decisions.pop(0)


def follow(text: str | None = "E qual foi o resultado?") -> ToolDecision:
    return ToolDecision(action="follow_up", follow_up_text=text, reason="faltou resultado")


def advance() -> ToolDecision:
    return ToolDecision(action="next_question", reason="cobriu")


def no_score(question: Question, answer: str) -> AnswerScore:
    raise AssertionError("scorer not used in this test")


def reply(state: InterviewState, text: str, decider: FakeDecider, minute: int = 1) -> StepResult:
    return answer(
        state,
        text,
        decider=decider,
        writer=fake_writer,
        scorer=no_score,
        clock=clock_at(T0 + timedelta(minutes=minute)),
    )


def test_follow_up_stays_on_question(plan: InterviewPlan) -> None:
    result = reply(started(plan), "Fiz um painel.", FakeDecider(follow()))
    assert result.next_turn.is_follow_up is True
    assert result.next_turn.question_id == "q1"
    assert result.next_turn.turn_no == 2
    assert result.next_turn.interviewer_text == "[opening] E qual foi o resultado?"
    assert result.state.follow_ups_used == 1
    assert result.state.turn_count == 2
    assert result.state.current_index == 0


def test_answered_turn_keeps_answer_and_decision(plan: InterviewPlan) -> None:
    result = reply(started(plan), "Fiz um painel.", FakeDecider(follow()))
    assert result.answered.turn_no == 1
    assert result.answered.answer_text == "Fiz um painel."
    assert result.answered.decision == follow()
    assert result.state.turns == [result.answered, result.next_turn]


def test_max_two_follow_ups_then_advance(plan: InterviewPlan) -> None:
    decider = FakeDecider(follow(), follow(), follow())
    state = started(plan)
    for _ in range(2):
        state = reply(state, "Resposta.", decider).state
    assert state.follow_ups_used == 2
    result = reply(state, "Resposta.", decider)
    assert result.next_turn.question_id == "q2"
    assert result.next_turn.is_follow_up is False
    assert result.state.follow_ups_used == 0
    assert result.answered.decision is not None
    assert result.answered.decision.action == "follow_up"  # original LLM decision kept


@pytest.mark.parametrize("text", [None, "", "   "])
def test_follow_up_without_text_advances(plan: InterviewPlan, text: str | None) -> None:
    decision = ToolDecision.model_construct(action="follow_up", follow_up_text=text, reason="x")
    result = reply(started(plan), "Resposta.", FakeDecider(decision))
    assert result.next_turn.question_id == "q2"


def test_next_question_advances_and_resets(plan: InterviewPlan) -> None:
    state = reply(started(plan), "Resposta.", FakeDecider(follow())).state
    result = reply(state, "Resposta.", FakeDecider(advance()))
    assert result.state.current_index == 1
    assert result.state.follow_ups_used == 0
    assert result.next_turn.question_id == "q2"
    assert result.next_turn.interviewer_text == f"[projects] {plan.questions[1].text}"


def test_early_end_from_llm_is_ignored(plan: InterviewPlan) -> None:
    decision = ToolDecision(action="end", reason="acho que basta")
    result = reply(started(plan), "Resposta.", FakeDecider(decision))
    assert result.state.ended is False
    assert result.next_turn.question_id == "q2"


def test_decider_gets_question_and_time(plan: InterviewPlan) -> None:
    decider = FakeDecider(advance())
    reply(started(plan), "Resposta.", decider, minute=5)
    question, _, status = decider.calls[0]
    assert question.id == "q1"
    assert status.minutes_left == pytest.approx(10.0)


def test_answer_is_masked_before_llm(plan: InterviewPlan) -> None:
    decider = FakeDecider(advance())
    result = reply(started(plan), "Meu e-mail é ana@exemplo.com.", decider)
    assert "ana@exemplo.com" not in decider.calls[0][1]
    assert "[EMAIL]" in decider.calls[0][1]
    assert result.answered.answer_text is not None
    assert "[EMAIL]" in result.answered.answer_text


@pytest.mark.parametrize("text", ["", "   \n"])
def test_empty_answer_rejected(plan: InterviewPlan, text: str) -> None:
    decider = FakeDecider()
    with pytest.raises(InterviewError):
        reply(started(plan), text, decider)
    assert decider.calls == []


def test_too_long_answer_rejected(plan: InterviewPlan) -> None:
    decider = FakeDecider()
    with pytest.raises(InterviewError):
        reply(started(plan), "a" * 4001, decider)
    assert decider.calls == []
    reply(started(plan), "a" * 4000, FakeDecider(advance()))  # limit itself is fine


def test_answer_on_ended_interview_rejected(plan: InterviewPlan) -> None:
    state = started(plan).model_copy(update={"ended": True, "end_reason": "visitor"})
    with pytest.raises(InterviewError):
        reply(state, "Resposta.", FakeDecider())


def test_answer_does_not_mutate_state(plan: InterviewPlan) -> None:
    state = started(plan)
    before = state.model_dump()
    reply(state, "Resposta.", FakeDecider(follow()))
    assert state.model_dump() == before


def test_writer_gets_recent_history_only(plan: InterviewPlan) -> None:
    seen: list[list[Turn]] = []

    def spy(phase: Phase, question: str, instruction: str, history: list[Turn]) -> str:
        seen.append(history)
        return question

    state, _ = start("s1", plan, writer=spy, clock=clock_at(T0))
    decider = FakeDecider(*[follow(), follow(), advance()] * 3)
    limits = InterviewLimits(history_turns=2)
    for _ in range(8):
        state = answer(
            state,
            "R.",
            decider=decider,
            writer=spy,
            scorer=no_score,
            clock=clock_at(T0),
            limits=limits,
        ).state
    assert all(len(h) <= 2 for h in seen)
    assert seen[-1][-1].answer_text == "R."


# --- endings and judge -------------------------------------------------------


def last_question_state(plan: InterviewPlan) -> InterviewState:
    return started(plan).model_copy(update={"current_index": len(plan.questions) - 1})


def test_plan_done_ends_with_closing_turn(plan: InterviewPlan) -> None:
    result = reply(last_question_state(plan), "Resposta.", FakeDecider(advance()))
    assert result.state.ended is True
    assert result.state.end_reason == "plan_done"
    assert result.next_turn.interviewer_text.startswith("[closing]")
    assert result.next_turn.question_id == plan.questions[-1].id
    assert result.next_turn.is_follow_up is False
    assert result.state.turns[-1] == result.next_turn
    assert result.state.turn_count == 2


def test_llm_end_on_last_question_ends(plan: InterviewPlan) -> None:
    decision = ToolDecision(action="end", reason="acabou")
    result = reply(last_question_state(plan), "Resposta.", FakeDecider(decision))
    assert result.state.ended is True
    assert result.state.end_reason == "plan_done"


def test_time_over_ends_without_calling_decider(plan: InterviewPlan) -> None:
    decider = FakeDecider()
    result = reply(started(plan), "Resposta.", decider, minute=16)
    assert decider.calls == []
    assert result.state.ended is True
    assert result.state.end_reason == "time_or_turns"
    assert result.answered.answer_text == "Resposta."
    assert result.answered.decision is None


def test_turn_limit_ends_without_calling_decider(plan: InterviewPlan) -> None:
    decider = FakeDecider()
    state = started(plan).model_copy(update={"turn_count": 30})
    result = reply(state, "Resposta.", decider)
    assert decider.calls == []
    assert result.state.end_reason == "time_or_turns"


def test_visitor_ends_without_model(plan: InterviewPlan) -> None:
    state = started(plan)
    ended, turn = end_interview(
        state, "visitor", writer=fake_writer, clock=clock_at(T0 + timedelta(minutes=2))
    )
    assert ended.ended is True
    assert ended.end_reason == "visitor"
    assert ended.turns[-1] == turn
    assert ended.turn_count == 2
    assert turn.turn_no == 2
    assert state.ended is False  # original untouched


def test_end_interview_twice_rejected(plan: InterviewPlan) -> None:
    ended, _ = end_interview(started(plan), "visitor", writer=fake_writer, clock=clock_at(T0))
    with pytest.raises(InterviewError):
        end_interview(ended, "visitor", writer=fake_writer, clock=clock_at(T0))


def good_score() -> AnswerScore:
    return AnswerScore(
        score=4,
        criteria_met=["c1"],
        evidence_quotes=["Fiz um painel."],
        justification="ok",
    )


def test_score_is_attached_to_answered_turn(plan: InterviewPlan) -> None:
    seen: list[tuple[str, str]] = []

    def scorer(question: Question, text: str) -> AnswerScore:
        seen.append((question.id, text))
        return good_score()

    result = answer(
        started(plan),
        "Fiz um painel. ana@exemplo.com",
        decider=FakeDecider(advance()),
        writer=fake_writer,
        scorer=scorer,
        clock=clock_at(T0),
    )
    assert result.answered.score == good_score()
    assert seen == [("q1", "Fiz um painel. [EMAIL]")]


def test_scorer_failure_does_not_block_next_turn(plan: InterviewPlan) -> None:
    def broken(question: Question, text: str) -> AnswerScore:
        raise RuntimeError("judge down")

    result = answer(
        started(plan),
        "Resposta.",
        decider=FakeDecider(advance()),
        writer=fake_writer,
        scorer=broken,
        clock=clock_at(T0),
    )
    assert result.answered.score is None
    assert result.next_turn.question_id == "q2"


def test_score_answer_swallows_errors(plan: InterviewPlan) -> None:
    def broken(question: Question, text: str) -> AnswerScore:
        raise ValueError("bad")

    assert score_answer(broken, plan.questions[0], "x") is None
    assert score_answer(lambda q, a: good_score(), plan.questions[0], "x") == good_score()


def test_time_over_still_scores_last_answer(plan: InterviewPlan) -> None:
    result = answer(
        started(plan),
        "Resposta.",
        decider=FakeDecider(),
        writer=fake_writer,
        scorer=lambda q, a: good_score(),
        clock=clock_at(T0 + timedelta(minutes=20)),
    )
    assert result.answered.score == good_score()


# --- real wiring: follow_up and interviewer prompts with a fake chat model ----


def _fake(reply: str) -> GenericFakeChatModel:
    return GenericFakeChatModel(messages=iter([AIMessage(content=reply)]))


def _records(runs_dir: Path) -> list[dict]:
    return [
        json.loads(line)
        for file in sorted(runs_dir.glob("*.jsonl"))
        for line in file.read_text(encoding="utf-8").splitlines()
        if line
    ]


def test_should_follow_up_returns_decision_and_logs_run(
    plan: InterviewPlan, tmp_path: Path
) -> None:
    reply = json.dumps(
        {"action": "follow_up", "follow_up_text": "E o resultado?", "reason": "faltou impacto"}
    )
    state = started(plan)
    decision = should_follow_up(
        plan.questions[0],
        "Fiz um dashboard.",
        state,
        TimeStatus(over=False, minutes_left=9.5),
        chat_model=_fake(reply),
        runs_dir=tmp_path,
    )
    assert decision == ToolDecision(
        action="follow_up", follow_up_text="E o resultado?", reason="faltou impacto"
    )
    records = _records(tmp_path)
    assert len(records) == 1
    assert records[0]["prompt_name"] == "follow_up"


def test_should_follow_up_passes_remaining_follow_ups_and_history(
    plan: InterviewPlan, tmp_path: Path
) -> None:
    reply = json.dumps({"action": "next_question", "reason": "ok"})
    state = started(plan).model_copy(update={"follow_ups_used": 1})
    should_follow_up(
        plan.questions[0],
        "Resposta de [EMAIL].",
        state,
        TimeStatus(over=False, minutes_left=5),
        chat_model=_fake(reply),
        runs_dir=tmp_path,
    )
    sent = json.dumps(_records(tmp_path)[0]["input"], ensure_ascii=False)
    assert plan.questions[0].look_for[0] in sent
    assert plan.questions[0].text in sent
    assert state.turns[0].interviewer_text in sent
    assert '"follow_ups_left": "1"' in sent
    assert '"minutes_left": "5.0"' in sent
    assert "[EMAIL]" in sent
    assert "ana@exemplo.com" not in sent


def test_default_writer_returns_speech_and_logs_run(plan: InterviewPlan, tmp_path: Path) -> None:
    writer = default_writer(
        persona=plan.persona, chat_model=_fake("Olá! Conte sobre você."), runs_dir=tmp_path
    )
    speech = writer("opening", "Conte sobre você.", "Faça a pergunta.", [])
    assert speech == "Olá! Conte sobre você."
    records = _records(tmp_path)
    assert len(records) == 1
    assert records[0]["prompt_name"] == "interviewer"
