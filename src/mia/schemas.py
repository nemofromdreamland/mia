"""Pydantic schemas shared across MIA (see docs/BACKEND_SCHEMA.md)."""

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    examples_seen: bool = False  # spec 5.6: neutral mark, never changes the score


# ---------- Service responses ----------


class SessionView(BaseModel):
    """GET /sessions/{id}: the session plus what the current status allows to show."""

    session: Session
    case: Case | None = None
    screening: Screening | None = None
    turns: list[PublicTurn] | None = None


class AnswerResult(BaseModel):
    turn: PublicTurn | None = None
    ended: bool = False


class ReportView(BaseModel):
    report: Report
    turns: list[Turn]
    is_above_case_avg: bool | None  # None without an average (< 3 completed sessions)
    examples_seen: bool = False  # spec 5.6: neutral note only


class RecruiterList(BaseModel):
    stats: list[CaseStats]
    candidates: list[RecruiterCandidateRow]


class RecruiterCandidate(BaseModel):
    row: RecruiterCandidateRow
    summary: CandidateSummary
    report: Report
    turns: list[Turn]
    examples_seen: bool = False  # spec 5.6: neutral note only, never a decision input


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


Split = Literal["dev", "test"]
AttackType = Literal[
    "answer_injection", "doc_injection", "personal_data", "format_variation", "off_topic"
]
_ANSWER_ATTACKS: frozenset[str] = frozenset(
    {"answer_injection", "personal_data", "format_variation"}
)
_TEXT_ATTACKS: frozenset[str] = frozenset({"off_topic"})


class _EvalModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ToolExpected(_EvalModel):
    action: Literal["follow_up", "next_question", "end"]
    follow_up_must_address: list[str] = []  # look_for items the follow-up must cover

    @model_validator(mode="after")
    def _address_matches_action(self) -> "ToolExpected":
        size = len(self.follow_up_must_address)
        if self.action == "follow_up" and not 1 <= size <= 2:
            raise ValueError("follow_up needs 1-2 follow_up_must_address items")
        if self.action != "follow_up" and size:
            raise ValueError("follow_up_must_address only applies to follow_up")
        return self


class ToolMomentItem(_EvalModel):
    """Set B item: one moment of the follow_up prompt and the expected decision."""

    item_id: str
    question_id: str
    answer: str
    follow_ups_left: int = Field(ge=0, le=2)
    minutes_left: float
    history: str
    expected: ToolExpected
    split: Split
    note: str

    @model_validator(mode="after")
    def _follow_up_needs_room(self) -> "ToolMomentItem":
        no_room = self.follow_ups_left == 0 or self.minutes_left <= 0
        if self.expected.action == "follow_up" and no_room:
            raise ValueError("follow_up expected but there is no room (follow-ups or time)")
        return self


class PlanExpected(_EvalModel):
    job_requirements: list[str] = Field(min_length=3, max_length=8)
    gap_keywords: list[str] = Field(min_length=1, max_length=4)


class PlanCaseItem(_EvalModel):
    """Set C item: a CV/job pair (paths from the repo root) and what the plan must cover."""

    item_id: str
    source: Literal["case", "extra"]
    cv_path: str
    job_path: str
    persona: Persona
    language: Language
    expected: PlanExpected
    split: Split


class RobustnessExpected(_EvalModel):
    max_score: int | None = Field(default=None, ge=1, le=5)
    forbidden_in_summary: list[str] = []
    must_not_contain: list[str] = []


class RobustnessItem(_EvalModel):
    """Set D item: an attack on the answer (judge/summary) or on the CV/job (CLI prep)."""

    item_id: str
    attack_type: AttackType
    question_id: str | None = None
    answer_text: str | None = None
    target: Literal["cv", "job"] | None = None
    base_case_id: str | None = None
    injected_text: str | None = None
    expected: RobustnessExpected
    split: Split
    note: str

    @model_validator(mode="after")
    def _fields_match_attack(self) -> "RobustnessItem":
        if self.attack_type in _ANSWER_ATTACKS:
            required = {
                "question_id": self.question_id,
                "answer_text": self.answer_text,
                "max_score": self.expected.max_score,
            }
        elif self.attack_type in _TEXT_ATTACKS:
            required = {"question_id": self.question_id, "answer_text": self.answer_text}
        else:
            required = {
                "target": self.target,
                "base_case_id": self.base_case_id,
                "injected_text": self.injected_text,
            }
        missing = [name for name, value in required.items() if value is None]
        if self.attack_type == "personal_data" and not self.expected.forbidden_in_summary:
            missing.append("forbidden_in_summary")
        if self.attack_type == "doc_injection" and not self.expected.must_not_contain:
            missing.append("must_not_contain")
        if missing:
            raise ValueError(f"{self.attack_type} requires: {', '.join(missing)}")
        return self


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


# ---------- Voice (spec 5) ----------


class VoiceConfig(BaseModel):
    """config/voice.yaml: which Sonic model/voice to use and the audio formats."""

    model_config = ConfigDict(extra="forbid")

    model_id: str
    region: str
    voice_id: str
    input_sample_rate: int = 16000
    output_sample_rate: int = 24000
    max_chunk_bytes: int = Field(default=4096, gt=0)


class _ClientEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SessionStartPayload(_ClientEvent):
    session_id: str = Field(min_length=1, max_length=64)


class AudioChunkPayload(_ClientEvent):
    data: str = Field(max_length=8192)  # base64; decoded size is checked by the /ws layer


class AudioMutePayload(_ClientEvent):
    muted: bool


class EmptyPayload(_ClientEvent):
    pass


class SessionStartEvent(_ClientEvent):
    type: Literal["session.start"]
    payload: SessionStartPayload


class AudioChunkEvent(_ClientEvent):
    type: Literal["audio.chunk"]
    payload: AudioChunkPayload


class AudioMuteEvent(_ClientEvent):
    type: Literal["audio.mute"]
    payload: AudioMutePayload


class SessionEndEvent(_ClientEvent):
    type: Literal["session.end"]
    payload: EmptyPayload = Field(default_factory=EmptyPayload)


class AnswerSubmitEvent(_ClientEvent):
    """Spec 5.6: the visitor clicked Enviar; the recorded audio was already sent."""

    type: Literal["answer.submit"]
    payload: EmptyPayload = Field(default_factory=EmptyPayload)


ClientEvent = Annotated[
    SessionStartEvent | AudioChunkEvent | AudioMuteEvent | SessionEndEvent | AnswerSubmitEvent,
    Field(discriminator="type"),
]

ServerEventType = Literal[
    "audio.output",
    "transcript",
    "interrupted",
    "state",
    "turn.saved",
    "session.ended",
    "error",
]


class ServerEvent(BaseModel):
    """Backend -> browser event (docs/BACKEND_SCHEMA.md, WebSocket); never a Sonic event."""

    type: ServerEventType
    payload: dict[str, Any] = Field(default_factory=dict)


class VoiceUrl(BaseModel):
    """POST /sessions/{id}/voice-url: signed WebSocket URL, valid for `expires_in` seconds."""

    url: str
    expires_in: int = 300


# ---------- Answer examples (spec 5.6) ----------


class AnswerExample(BaseModel):
    """Example answers for one plan question: a strong and a weak one, generated beforehand."""

    model_config = ConfigDict(extra="forbid")

    question_id: str
    strong: str = Field(min_length=1)
    weak: str = Field(min_length=1)


class CaseExamples(BaseModel):
    """cases/<id>/examples.json."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    generated_by: str  # "<prompt>@v<N> <model>"
    examples: list[AnswerExample]


class ExamplesView(BaseModel):
    """GET /sessions/{id}/examples: examples for the current question only."""

    question_id: str
    strong: str
    weak: str
