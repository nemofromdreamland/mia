"""Judge: scores an interview answer against the question's look_for criteria.

The LLM drafts the AnswerScore; the code decides what survives: criteria must come
from look_for and every evidence quote must exist literally in the answer.
"""

from mia.checks import quote_in_source
from mia.schemas import AnswerScore, Question


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
