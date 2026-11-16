"""Tests for the judge: deterministic checks on the LLM's AnswerScore."""

from mia.judge import verify_score
from mia.schemas import AnswerScore, Question

QUESTION = Question(
    id="q1",
    phase="projects",
    competency="Python",
    text="Conte um projeto em que você melhorou a performance.",
    purpose="Checar profundidade técnica.",
    look_for=["cita exemplo concreto", "mede resultado", "explica trade-off"],
    follow_ups=[],
)
ANSWER = "No projeto X reduzi a latência em 30% usando cache."


def make_score(
    quotes: list[str],
    criteria: list[str] | None = None,
    quotes_verified: bool | None = None,
) -> AnswerScore:
    return AnswerScore(
        score=4,
        criteria_met=criteria if criteria is not None else ["mede resultado"],
        evidence_quotes=quotes,
        justification="Exemplo concreto com resultado medido.",
        quotes_verified=quotes_verified,
    )


def test_all_quotes_literal_is_verified() -> None:
    result = verify_score(make_score(["reduzi a latência em 30%"]), QUESTION, ANSWER)
    assert result.evidence_quotes == ["reduzi a latência em 30%"]
    assert result.criteria_met == ["mede resultado"]
    assert result.quotes_verified is True
    assert result.score == 4


def test_invented_quote_is_dropped_and_flagged() -> None:
    score = make_score(["reduzi a latência em 30%", "aumentei a receita"])
    result = verify_score(score, QUESTION, ANSWER)
    assert result.evidence_quotes == ["reduzi a latência em 30%"]
    assert result.quotes_verified is False


def test_paraphrased_quote_is_dropped() -> None:
    result = verify_score(make_score(["diminuí a latência"]), QUESTION, ANSWER)
    assert result.evidence_quotes == []
    assert result.quotes_verified is False


def test_quote_with_cosmetic_differences_is_kept() -> None:
    answer = "Eu disse “usar cache”\ne reduzi a latência."
    score = make_score(['disse "usar cache" e reduzi'])
    result = verify_score(score, QUESTION, answer)
    assert result.evidence_quotes == ['disse "usar cache" e reduzi']
    assert result.quotes_verified is True


def test_criteria_outside_look_for_are_removed() -> None:
    score = make_score(["reduzi a latência em 30%"], ["mede resultado", "é simpático"])
    result = verify_score(score, QUESTION, ANSWER)
    assert result.criteria_met == ["mede resultado"]


def test_criteria_with_surrounding_spaces_are_accepted() -> None:
    score = make_score(["reduzi a latência em 30%"], [" mede resultado "])
    result = verify_score(score, QUESTION, ANSWER)
    assert result.criteria_met == ["mede resultado"]


def test_empty_quotes_are_verified_and_score_kept() -> None:
    result = verify_score(make_score([]), QUESTION, ANSWER)
    assert result.quotes_verified is True
    assert result.score == 4
    assert result.criteria_met == ["mede resultado"]


def test_llm_quotes_verified_value_is_ignored() -> None:
    score = make_score(["reduzi a latência em 30%"], quotes_verified=False)
    assert verify_score(score, QUESTION, ANSWER).quotes_verified is True


def test_input_score_is_not_mutated() -> None:
    score = make_score(["aumentei a receita"])
    verify_score(score, QUESTION, ANSWER)
    assert score.evidence_quotes == ["aumentei a receita"]
    assert score.quotes_verified is None
