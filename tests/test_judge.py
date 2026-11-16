"""Tests for the judge: deterministic checks on the LLM's AnswerScore."""

import json
from pathlib import Path

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from mia.interviewer import score_answer
from mia.judge import default_scorer, judge_answer, verify_score
from mia.llm import LLMInvalidOutputError
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


# --- judge_answer / default_scorer with a fake chat model ----------------------


def _fake(*replies: str) -> GenericFakeChatModel:
    return GenericFakeChatModel(messages=iter([AIMessage(content=r) for r in replies]))


def _records(runs_dir: Path) -> list[dict]:
    return [
        json.loads(line)
        for file in sorted(runs_dir.glob("*.jsonl"))
        for line in file.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _reply(quotes: list[str], criteria: list[str] | None = None) -> str:
    return json.dumps(
        {
            "score": 4,
            "criteria_met": criteria if criteria is not None else ["mede resultado"],
            "evidence_quotes": quotes,
            "justification": "Exemplo concreto com resultado medido.",
        },
        ensure_ascii=False,
    )


def test_judge_answer_returns_verified_score(tmp_path: Path) -> None:
    reply = _reply(["reduzi a latência em 30%", "aumentei a receita"], ["mede resultado", "x"])
    result = judge_answer(QUESTION, ANSWER, chat_model=_fake(reply), runs_dir=tmp_path)
    assert result.evidence_quotes == ["reduzi a latência em 30%"]
    assert result.criteria_met == ["mede resultado"]
    assert result.quotes_verified is False


def test_judge_answer_sends_question_and_joined_look_for(tmp_path: Path) -> None:
    judge_answer(QUESTION, ANSWER, chat_model=_fake(_reply([])), runs_dir=tmp_path)
    sent = _records(tmp_path)[0]["input"]
    variables = json.dumps(sent, ensure_ascii=False)
    assert QUESTION.text in variables
    assert "cita exemplo concreto; mede resultado; explica trade-off" in variables
    assert ANSWER in variables


def test_judge_answer_masks_pii_before_the_call_and_verifies_against_it(tmp_path: Path) -> None:
    answer = "Escreva para ana@exemplo.com: reduzi a latência em 30%."
    reply = _reply(["Escreva para [EMAIL]: reduzi"])
    result = judge_answer(QUESTION, answer, chat_model=_fake(reply), runs_dir=tmp_path)
    sent = json.dumps(_records(tmp_path)[0]["input"], ensure_ascii=False)
    assert "[EMAIL]" in sent
    assert "ana@exemplo.com" not in sent
    assert result.quotes_verified is True


def test_judge_answer_raises_when_repair_fails(tmp_path: Path) -> None:
    with pytest.raises(LLMInvalidOutputError):
        judge_answer(QUESTION, ANSWER, chat_model=_fake("lixo", "lixo"), runs_dir=tmp_path)


def test_judge_answer_logs_run_record(tmp_path: Path) -> None:
    judge_answer(
        QUESTION, ANSWER, session_id="s-1", chat_model=_fake(_reply([])), runs_dir=tmp_path
    )
    records = _records(tmp_path)
    assert len(records) == 1
    assert records[0]["prompt_name"] == "judge"
    assert records[0]["prompt_version"] == 1
    assert records[0]["session_id"] == "s-1"


def test_default_scorer_fills_score_through_interviewer(tmp_path: Path) -> None:
    scorer = default_scorer(
        chat_model=_fake(_reply(["reduzi a latência em 30%"])), runs_dir=tmp_path
    )
    score = score_answer(scorer, QUESTION, ANSWER)
    assert score is not None
    assert score.quotes_verified is True
    assert score.evidence_quotes == ["reduzi a latência em 30%"]


# --- prompt_version (task 2.9) -------------------------------------------------


def test_judge_answer_uses_default_prompt_version(tmp_path: Path) -> None:
    judge_answer(QUESTION, ANSWER, chat_model=_fake(_reply([])), runs_dir=tmp_path)
    assert _records(tmp_path)[0]["prompt_version"] == 1


def test_judge_answer_loads_requested_prompt_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import mia.judge as judge_module

    seen: list[tuple[str, int]] = []
    real_load = judge_module.load_prompt

    def spy(name: str, version: int, **kwargs: object) -> object:
        seen.append((name, version))
        return real_load(name, 1)

    monkeypatch.setattr(judge_module, "load_prompt", spy)
    judge_answer(
        QUESTION, ANSWER, prompt_version=2, chat_model=_fake(_reply([])), runs_dir=tmp_path
    )
    assert seen == [("judge", 2)]


def test_judge_answer_unknown_prompt_version_fails(tmp_path: Path) -> None:
    from mia.prompts import PromptError

    with pytest.raises(PromptError, match="v99"):
        judge_answer(
            QUESTION, ANSWER, prompt_version=99, chat_model=_fake(_reply([])), runs_dir=tmp_path
        )
