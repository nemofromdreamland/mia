"""Report graph: turns -> scores -> per-competency aggregation -> report + candidate summary.

The LLM drafts the texts; the code decides the numbers, which items survive and
whether the anonymous summary is acceptable.
"""

import json
import re
from pathlib import Path
from statistics import mean
from typing import Any, Final, TypedDict

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel

from mia.checks import quote_in_source
from mia.interviewer import Scorer, score_answer
from mia.llm import DEFAULT_RUNS_DIR
from mia.pii import CPF, EMAIL, NAME, PHONE, URL, mask_text
from mia.prompts import load_prompt, run_prompt_structured
from mia.schemas import (
    CandidateSummary,
    CompetencyScore,
    InterviewPlan,
    Question,
    Report,
    SummaryPoint,
    Turn,
)

REPORT_PROMPT: Final = ("report", 1)
SUMMARY_PROMPT: Final = ("candidate_summary", 1)
_PLACEHOLDERS: Final = (EMAIL, PHONE, CPF, URL, NAME)
# Age and explicit gender only; pronouns ("ele"/"ela") are left out on purpose (false positives).
_AGE_GENDER_RE: Final = re.compile(
    r"\d+\s*anos|\b(?:idade|jovem|idoso|homem|mulher|masculino|feminino|a candidata)\b",
    re.IGNORECASE,
)


class ReportError(Exception):
    """The report cannot be built from these turns."""


class ReportValidationError(ReportError):
    """The drafted report or summary broke a rule the code enforces."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


class ReportResult(BaseModel):
    report: Report
    summary: CandidateSummary
    turns: list[Turn]


class ReportState(TypedDict, total=False):
    plan: InterviewPlan
    turns: list[Turn]
    competency_scores: dict[str, float]
    overall_score: float
    transcript: str  # masked
    report: Report
    summary: CandidateSummary
    problems: list[str]


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


def apply_report_rules(
    report: Report, competency_scores: dict[str, float], overall: float, answered_ids: set[str]
) -> Report:
    """Force the code's numbers, drop unknown competencies and orphan improvements."""
    drafted = {item.competency: item for item in report.competencies}
    missing = [name for name in competency_scores if name not in drafted]
    if missing:
        raise ReportValidationError([f"report is missing competencies: {', '.join(missing)}"])
    competencies = [
        CompetencyScore(competency=name, score=score, summary=drafted[name].summary)
        for name, score in competency_scores.items()
    ]
    improvements = [i for i in report.improvements if i.question_id in answered_ids]
    return report.model_copy(
        update={
            "overall_score": overall,
            "competencies": competencies,
            "improvements": improvements,
        }
    )


def _verified(points: list[SummaryPoint], answers_masked: list[str]) -> list[SummaryPoint]:
    return [
        point
        for point in points
        if any(quote_in_source(point.answer_quote, answer) for answer in answers_masked)
    ]


def verify_summary(summary: CandidateSummary, answers_masked: list[str]) -> CandidateSummary:
    """Keep only points whose quote exists in an answer; an emptied list is an error."""
    strengths = _verified(summary.strengths, answers_masked)
    concerns = _verified(summary.concerns, answers_masked)
    problems = [
        f"no verifiable quote left in {name}"
        for name, kept in (("strengths", strengths), ("concerns", concerns))
        if not kept
    ]
    if problems:
        raise ReportValidationError(problems)
    return summary.model_copy(update={"strengths": strengths, "concerns": concerns})


def _summary_texts(summary: CandidateSummary) -> list[tuple[str, str]]:
    fields = [
        ("headline", summary.headline),
        ("summary", summary.summary),
        ("next_step_reason", summary.next_step_reason),
    ]
    for kind, points in (("strengths", summary.strengths), ("concerns", summary.concerns)):
        fields += [(f"{kind}[{i}].point", point.point) for i, point in enumerate(points)]
    return fields


def personal_data_problems(summary: CandidateSummary) -> list[str]:
    """Personal data, gender or age mentions in the recruiter-facing texts."""
    problems = []
    for field, text in _summary_texts(summary):
        if mask_text(text) != text or any(mark in text for mark in _PLACEHOLDERS):
            problems.append(f"{field}: contains personal data")
        if _AGE_GENDER_RE.search(text):
            problems.append(f"{field}: mentions age or gender")
    return problems


def _scores_json(plan: InterviewPlan, turns: list[Turn]) -> str:
    questions = _questions(plan)
    rows = [
        {
            "question_id": turn.question_id,
            "competency": _question_for(questions, turn).competency,
            "score": turn.score.score,
        }
        for turn in turns
        if turn.score is not None
    ]
    return json.dumps(rows, ensure_ascii=False)


def build_report_graph(
    *,
    scorer: Scorer,
    model: str | None = None,
    experiment: str | None = None,
    session_id: str | None = None,
    runs_dir: Path = DEFAULT_RUNS_DIR,
    chat_model: BaseChatModel | None = None,
) -> CompiledStateGraph:
    """Straight-line graph: ensure scores -> aggregate -> report -> summary -> validate."""
    report_prompt = load_prompt(*REPORT_PROMPT)
    summary_prompt = load_prompt(*SUMMARY_PROMPT)
    call_options: dict[str, Any] = {
        "model": model,
        "experiment": experiment,
        "session_id": session_id,
        "runs_dir": runs_dir,
        "chat_model": chat_model,
    }

    def _ensure_scores(state: ReportState) -> ReportState:
        return {"turns": ensure_scores(state["plan"], state["turns"], scorer)}

    def _aggregate(state: ReportState) -> ReportState:
        scores, overall = aggregate_scores(state["plan"], state["turns"])
        return {
            "competency_scores": scores,
            "overall_score": overall,
            "transcript": build_transcript(state["plan"], state["turns"]),
        }

    def _report(state: ReportState) -> ReportState:
        drafted = run_prompt_structured(
            report_prompt,
            {
                "competencies": ", ".join(state["competency_scores"]),
                "scores": _scores_json(state["plan"], state["turns"]),
                "transcript": state["transcript"],
            },
            Report,
            **call_options,
        )
        answered = {t.question_id for t in state["turns"] if t.answer_text is not None}
        report = apply_report_rules(
            drafted, state["competency_scores"], state["overall_score"], answered
        )
        return {"report": report}

    def _summary(state: ReportState) -> ReportState:
        drafted = run_prompt_structured(
            summary_prompt,
            {
                "overall_score": str(state["overall_score"]),
                "scores": _scores_json(state["plan"], state["turns"]),
                "transcript": state["transcript"],
            },
            CandidateSummary,
            **call_options,
        )
        masked = [mask_text(t.answer_text) for t in state["turns"] if t.answer_text is not None]
        return {"summary": verify_summary(drafted, masked)}

    def _validate(state: ReportState) -> ReportState:
        return {"problems": personal_data_problems(state["summary"])}

    steps = [
        ("ensure_scores", _ensure_scores),
        ("aggregate", _aggregate),
        ("report", _report),
        ("summary", _summary),
        ("validate", _validate),
    ]
    graph = StateGraph(ReportState)
    for name, node in steps:
        graph.add_node(name, node)
    names = [name for name, _ in steps]
    graph.add_edge(START, names[0])
    for current, following in zip(names, names[1:], strict=False):
        graph.add_edge(current, following)
    graph.add_edge(names[-1], END)
    return graph.compile()


def run_report(plan: InterviewPlan, turns: list[Turn], **graph_options: Any) -> ReportResult:
    """Build the report and the anonymous summary; raise ReportError if a rule is broken."""
    state = build_report_graph(**graph_options).invoke({"plan": plan, "turns": turns})
    if state["problems"]:
        raise ReportValidationError(state["problems"])
    return ReportResult(report=state["report"], summary=state["summary"], turns=state["turns"])
