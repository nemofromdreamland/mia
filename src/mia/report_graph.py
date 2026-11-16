"""Report graph: turns -> scores -> per-competency aggregation -> report + candidate summary.

The LLM drafts the texts; the code decides the numbers, which items survive and
whether the anonymous summary is acceptable.
"""

from statistics import mean

from mia.interviewer import Scorer, score_answer
from mia.pii import mask_text
from mia.schemas import InterviewPlan, Question, Turn


class ReportError(Exception):
    """The report cannot be built from these turns."""


def _questions(plan: InterviewPlan) -> dict[str, Question]:
    return {question.id: question for question in plan.questions}


def _question_for(questions: dict[str, Question], turn: Turn) -> Question:
    try:
        return questions[turn.question_id]
    except KeyError:
        raise ReportError(f"turn {turn.turn_no}: unknown question_id {turn.question_id}") from None


def ensure_scores(plan: InterviewPlan, turns: list[Turn], scorer: Scorer) -> list[Turn]:
    """Score answered turns that have no score yet; a judge failure leaves the turn unscored."""
    questions = _questions(plan)
    result = []
    for turn in turns:
        if turn.answer_text is not None and turn.score is None:
            score = score_answer(scorer, _question_for(questions, turn), turn.answer_text)
            turn = turn.model_copy(update={"score": score})
        result.append(turn)
    return result


def aggregate_scores(plan: InterviewPlan, turns: list[Turn]) -> tuple[dict[str, float], float]:
    """Mean score per competency (1 decimal) and overall = mean of the competencies."""
    questions = _questions(plan)
    by_competency: dict[str, list[int]] = {}
    for turn in turns:
        if turn.score is not None:
            competency = _question_for(questions, turn).competency
            by_competency.setdefault(competency, []).append(turn.score.score)
    if not by_competency:
        raise ReportError("no scored turns to build a report from")
    means = {name: mean(values) for name, values in by_competency.items()}
    overall = round(mean(means.values()), 1)
    return {name: round(value, 1) for name, value in means.items()}, overall


def build_transcript(plan: InterviewPlan, turns: list[Turn]) -> str:
    """Question and masked answer of each answered turn, in order."""
    blocks = [
        f"Pergunta ({turn.question_id}): {turn.interviewer_text}\n"
        f"Resposta: {mask_text(turn.answer_text)}"
        for turn in turns
        if turn.answer_text is not None
    ]
    return "\n\n".join(blocks)
