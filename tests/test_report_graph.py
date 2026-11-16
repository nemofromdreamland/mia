"""Tests for the report graph: deterministic scoring, aggregation and checks."""

import json
from pathlib import Path

import pytest

from mia.report_graph import (
    ReportError,
    aggregate_scores,
    build_transcript,
    ensure_scores,
)
from mia.schemas import AnswerScore, InterviewPlan, Question, Turn

FIXTURES = Path(__file__).parent / "fixtures"


def load_plan() -> InterviewPlan:
    return InterviewPlan.model_validate_json(
        (FIXTURES / "prep" / "plan_ok.json").read_text(encoding="utf-8")
    )


def load_turns() -> list[Turn]:
    raw = json.loads((FIXTURES / "report" / "turns.json").read_text(encoding="utf-8"))
    return [Turn.model_validate(item) for item in raw]


def fixed_scorer(value: int = 2):
    calls: list[tuple[str, str]] = []

    def scorer(question: Question, answer: str) -> AnswerScore:
        calls.append((question.id, answer))
        return AnswerScore(score=value, criteria_met=[], evidence_quotes=[], justification="x")

    return scorer, calls


def scored(turns: list[Turn], *values: int | None) -> list[Turn]:
    """Replace the score of each answered turn, in order."""
    answered = iter(values)
    result = []
    for turn in turns:
        if turn.answer_text is None:
            result.append(turn)
            continue
        value = next(answered)
        score = (
            None
            if value is None
            else AnswerScore(score=value, criteria_met=[], evidence_quotes=[], justification="x")
        )
        result.append(turn.model_copy(update={"score": score}))
    return result


# ---------- ensure_scores ----------


def test_ensure_scores_fills_only_missing_answered_turns() -> None:
    plan, turns = load_plan(), load_turns()
    scorer, calls = fixed_scorer(2)

    result = ensure_scores(plan, turns, scorer)

    assert calls == [("q2", "Usei pandas para limpar os dados e Streamlit para o painel.")]
    assert result[1].score is not None and result[1].score.score == 2
    assert [t.score.score for t in result if t.score] == [4, 2, 3, 5]
    assert result[4].score is None  # closing turn has no answer
    assert turns[1].score is None  # input not mutated


def test_ensure_scores_skips_turn_when_scorer_fails() -> None:
    def broken(question: Question, answer: str) -> AnswerScore:
        raise RuntimeError("judge down")

    result = ensure_scores(load_plan(), load_turns(), broken)

    assert result[1].score is None
    assert result[0].score is not None


def test_ensure_scores_unknown_question_raises() -> None:
    turns = load_turns()
    turns[1] = turns[1].model_copy(update={"question_id": "q99"})
    scorer, _ = fixed_scorer()

    with pytest.raises(ReportError, match="q99"):
        ensure_scores(load_plan(), turns, scorer)


# ---------- aggregate_scores ----------


def test_aggregate_scores_by_competency_and_overall() -> None:
    plan = load_plan()
    # q1 (Comunicação)=4, q2 (Python)=2, q2 follow-up=3, q3 (RAG)=5
    turns = scored(load_turns(), 4, 2, 3, 5)

    competencies, overall = aggregate_scores(plan, turns)

    assert competencies == {"Comunicação de resultados": 4.0, "Python": 2.5, "RAG": 5.0}
    assert overall == 3.8  # (4 + 2.5 + 5) / 3 = 3.83


def test_aggregate_scores_ignores_unscored_turns() -> None:
    turns = scored(load_turns(), None, 2, None, 4)

    competencies, overall = aggregate_scores(load_plan(), turns)

    assert competencies == {"Python": 2.0, "RAG": 4.0}
    assert overall == 3.0


def test_aggregate_scores_without_scores_raises() -> None:
    turns = scored(load_turns(), None, None, None, None)

    with pytest.raises(ReportError):
        aggregate_scores(load_plan(), turns)


# ---------- build_transcript ----------


def test_build_transcript_masks_answers_and_skips_unanswered() -> None:
    transcript = build_transcript(load_plan(), load_turns())

    assert "ana.teste@example.com" not in transcript
    assert "98765-4321" not in transcript
    assert "[EMAIL]" in transcript and "[TELEFONE]" in transcript
    assert "Pergunta (q2): Que decisão técnica você mudaria hoje?" in transcript
    assert "terminou" not in transcript  # closing turn without answer
    assert transcript.index("(q1)") < transcript.index("(q3)")
