"""Pydantic schemas shared across MIA (see docs/BACKEND_SCHEMA.md)."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Persona = Literal["hr", "technical", "manager"]
Language = Literal["pt-BR", "en-US"]
Mode = Literal["text", "voice"]
Level = Literal["internship", "junior", "mid"]
SessionStatus = Literal[
    "preparing", "ready", "in_progress", "scoring", "completed", "failed", "abandoned"
]
Phase = Literal["opening", "projects", "technical", "behavioral", "candidate_questions", "closing"]


# ---------- Cases ----------


class Case(BaseModel):
    """One of the 5 ready-made demo cases (cases/<case_id>/case.yaml)."""

    case_id: str
    title: str
    company: str
    level: Level
    persona: Persona
    language: Language = "pt-BR"
    blurb: str  # the job in one sentence
    candidate_blurb: str  # who the visitor plays
    estimated_minutes: int
    version: int


class CaseSummary(BaseModel):
    """What GET /cases returns: no CV, no plan."""

    case_id: str
    title: str
    company: str
    level: Level
    persona: Persona
    blurb: str
    candidate_blurb: str
    estimated_minutes: int
    completed_sessions: int


# ---------- Preparation ----------


class Evidence(BaseModel):
    point: str
    cv_quote: str  # must exist verbatim in the CV (checked by code)


class Screening(BaseModel):
    job_title: str
    fit_score: int = Field(ge=0, le=100)
    strengths: list[Evidence] = Field(min_length=1, max_length=5)
    concerns: list[Evidence] = Field(min_length=1, max_length=5)
    missing_keywords: list[str]
    competencies: list[str] = Field(min_length=3, max_length=6)


class Question(BaseModel):
    id: str
    phase: Phase
    competency: str
    text: str
    purpose: str
    look_for: list[str] = Field(min_length=3, max_length=4)
    follow_ups: list[str] = Field(max_length=3)
    targets_concern: str | None = None


class InterviewPlan(BaseModel):
    persona: Persona
    language: Language
    estimated_minutes: int = Field(ge=5, le=45)
    questions: list[Question] = Field(min_length=4, max_length=12)


# ---------- Interview ----------


class ToolDecision(BaseModel):
    action: Literal["follow_up", "next_question", "end"]
    follow_up_text: str | None = None
    reason: str


class AnswerScore(BaseModel):
    score: int = Field(ge=1, le=5)
    criteria_met: list[str]
    evidence_quotes: list[str]
    justification: str
    quotes_verified: bool | None = None  # filled in by code


class Turn(BaseModel):
    session_id: str
    turn_no: int
    question_id: str
    interviewer_text: str
    answer_text: str | None = None
    is_follow_up: bool = False
    decision: ToolDecision | None = None
    score: AnswerScore | None = None
    latency_ms: int | None = None
    created_at: datetime


class PublicTurn(BaseModel):
    """Turn as the frontend sees it DURING the interview: no score, decision or follow-up flag."""

    turn_no: int
    question_id: str
    interviewer_text: str
    answer_text: str | None = None
    created_at: datetime


# ---------- Report ----------


class CompetencyScore(BaseModel):
    competency: str
    score: float = Field(ge=1, le=5)
    summary: str


class Improvement(BaseModel):
    question_id: str
    issue: str
    stronger_answer: str


class Report(BaseModel):
    overall_score: float = Field(ge=1, le=5)
    competencies: list[CompetencyScore]
    strengths: list[str]
    improvements: list[Improvement]


# ---------- Recruiter ----------


class SummaryPoint(BaseModel):
    point: str
    answer_quote: str  # must exist verbatim in an answer (checked by code)


class CandidateSummary(BaseModel):
    headline: str = Field(max_length=140)  # one sentence
    summary: str  # 3 to 4 sentences about the performance
    strengths: list[SummaryPoint] = Field(min_length=1, max_length=3)
    concerns: list[SummaryPoint] = Field(min_length=1, max_length=3)
    suggested_next_step: Literal["advance", "advance_with_caution", "not_now"]
    next_step_reason: str


class CaseStats(BaseModel):
    case_id: str
    completed_sessions: int
    average_score: float | None  # None with fewer than 3 completed sessions


class RecruiterCandidateRow(BaseModel):
    session_id: str
    case_id: str
    candidate_no: int
    ended_at: datetime
    overall_score: float
    delta_vs_case_avg: float | None  # overall_score - average_score
    headline: str


# ---------- Session ----------


class Session(BaseModel):
    visitor_id: str
    session_id: str
    case_id: str | None = None
    case_version: int | None = None
    candidate_no: int | None = None
    status: SessionStatus
    persona: Persona
    language: Language
    mode: Mode
    job_title: str | None = None
    fit_score: int | None = None
    overall_score: float | None = None
    competency_scores: dict[str, float] = Field(default_factory=dict)
    headline: str | None = None
    current_question_id: str | None = None
    follow_ups_used: int = 0
    turn_count: int = 0
    prompt_versions: dict[str, int] = Field(default_factory=dict)
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    ended_at: datetime | None = None


# ---------- Evaluation ----------


Variant = Literal["level_5", "level_4", "level_3", "level_2", "level_1", "rambling", "paraphrase"]


class GoldenItem(BaseModel):
    """Golden set A item. human_score and split stay None until human review (task 2.3)."""

    item_id: str
    question: Question
    answer_text: str
    variant: Variant
    paraphrase_of: str | None
    human_score: int | None = Field(default=None, ge=1, le=5)
    split: Literal["dev", "test"] | None = None
    generated_by: str


# ---------- Runs ----------


class RunRecord(BaseModel):
    """One line per model call in runs/<date>_<experiment>.jsonl."""

    run_id: str
    experiment: str | None
    session_id: str | None
    prompt_name: str
    prompt_version: int
    provider: Literal["bedrock", "gemini", "groq"]
    model: str
    params: dict[str, Any]
    input_hash: str
    input: dict[str, Any]  # masked variables
    output_raw: str
    output_parsed: dict[str, Any] | None
    json_valid_first_try: bool | None  # None = not applicable (free-text output)
    repaired: bool | None  # None = not applicable (free-text output)
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost_usd: float
    error: str | None
    created_at: datetime
