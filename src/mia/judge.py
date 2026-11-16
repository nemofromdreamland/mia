"""Judge: scores an interview answer against the question's look_for criteria.

The LLM drafts the AnswerScore; the code decides what survives: criteria must come
from look_for and every evidence quote must exist literally in the answer.
"""

from typing import Any, Final

from mia.checks import quote_in_source
from mia.interviewer import Scorer
from mia.pii import mask_text
from mia.prompts import load_prompt, run_prompt_structured
from mia.schemas import AnswerScore, Question

JUDGE_PROMPT: Final = ("judge", 1)


def verify_score(score: AnswerScore, question: Question, answer: str) -> AnswerScore:
    """Pure: filter criteria_met to look_for, drop unverified quotes, set quotes_verified."""
    allowed = set(question.look_for)
    criteria = [item.strip() for item in score.criteria_met if item.strip() in allowed]
    quotes = [quote for quote in score.evidence_quotes if quote_in_source(quote, answer)]
    return score.model_copy(
        update={
            "criteria_met": criteria,
            "evidence_quotes": quotes,
            "quotes_verified": len(quotes) == len(score.evidence_quotes),
        }
    )


def judge_answer(
    question: Question,
    answer: str,
    *,
    session_id: str | None = None,
    params: dict[str, Any] | None = None,
    prompt_version: int | None = None,
    **llm_options: Any,
) -> AnswerScore:
    """Mask the answer, ask the judge prompt, then verify what the LLM returned.

    prompt_version picks prompts/judge/v<N>.yaml (evals only); None = JUDGE_PROMPT.
    """
    name, default_version = JUDGE_PROMPT
    masked = mask_text(answer)
    variables = {
        "question": question.text,
        "look_for": "; ".join(question.look_for),
        "answer": masked,
    }
    score = run_prompt_structured(
        load_prompt(name, prompt_version or default_version),
        variables,
        AnswerScore,
        session_id=session_id,
        params=params,
        **llm_options,
    )
    return verify_score(score, question, masked)


def default_scorer(**llm_options: Any) -> Scorer:
    """Scorer for the interviewer (1.7) backed by the real judge."""

    def score(question: Question, answer: str) -> AnswerScore:
        return judge_answer(question, answer, **llm_options)

    return score
