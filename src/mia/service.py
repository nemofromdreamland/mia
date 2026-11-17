"""Service layer: the 11 operations of the API, with no HTTP.

The service applies the session lifecycle rules. It keeps no state between calls and
receives every dependency (repositories, models, clock) through `ServiceDeps`.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from mia.cases import CaseError, CaseNotFoundError, load_case
from mia.cases import list_cases as load_cases
from mia.interviewer import (
    DEFAULT_LIMITS,
    Clock,
    Decider,
    InterviewError,
    InterviewState,
    Scorer,
    Writer,
    answer,
    start,
)
from mia.interviewer import end_interview as close_interview
from mia.llm import LLMInvalidOutputError
from mia.recruiter import (
    above_average_rows,
    build_row,
    case_average,
    case_stats,
    is_above_average,
    sort_rows,
)
from mia.report_graph import ReportError, ReportResult
from mia.repositories import (
    CandidateCounter,
    ReportStore,
    SessionConflictError,
    SessionNotFoundError,
    SessionRepository,
)
from mia.schemas import (
    AnswerResult,
    CaseStats,
    CaseSummary,
    InterviewPlan,
    Mode,
    Persona,
    PublicTurn,
    RecruiterCandidate,
    RecruiterCandidateRow,
    RecruiterList,
    ReportView,
    Session,
    SessionStatus,
    SessionView,
    Turn,
)
from mia.simulation import new_session_id

SESSION_MAX_MINUTES = 45  # session_limit; the interviewer's own closing (<= 15 min) is separate

ErrorCode = Literal[
    "not_found",
    "invalid_input",
    "invalid_state",
    "session_limit",
    "quota_exceeded",
    "demo_paused",
    "llm_invalid_output",
    "provider_unavailable",
    "internal",
]


class ServiceError(Exception):
    """Business error with a stable code; the API (3.2) turns it into HTTP."""

    def __init__(self, code: ErrorCode, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


@runtime_checkable
class SessionGate(Protocol):
    """Quota + kill switch checked before a session is created (real one: 3.4)."""

    def check(self, visitor_id: str) -> None: ...  # raises ServiceError when it refuses


class OpenGate:
    """Gate that always allows (placeholder until 3.4)."""

    def check(self, visitor_id: str) -> None:
        return None


class ServiceDeps(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    repo: SessionRepository
    reports: ReportStore
    counter: CandidateCounter
    gate: SessionGate
    decider: Decider
    writer_for: Callable[[Persona], Writer]
    scorer: Scorer
    report: Callable[[InterviewPlan, list[Turn]], ReportResult]
    clock: Clock
    cases_dir: Path


@contextmanager
def _session_lookup() -> Iterator[None]:
    """A missing session and another visitor's session look the same: not_found."""
    try:
        yield
    except SessionNotFoundError as exc:
        raise ServiceError("not_found", "Sessão não encontrada.") from exc


def to_public(turn: Turn) -> PublicTurn:
    """Drop what must not leave the server before the report (score, decision, follow-up)."""
    return PublicTurn(
        turn_no=turn.turn_no,
        question_id=turn.question_id,
        interviewer_text=turn.interviewer_text,
        answer_text=turn.answer_text,
        created_at=turn.created_at,
    )


def list_cases(deps: ServiceDeps) -> list[CaseSummary]:
    completed = deps.repo.list_completed()
    summaries: list[CaseSummary] = []
    for case in load_cases(deps.cases_dir):
        done = sum(1 for s in completed if s.case_id == case.case_id)
        summaries.append(
            CaseSummary(
                **case.model_dump(include=set(CaseSummary.model_fields)), completed_sessions=done
            )
        )
    return summaries


def create_session(deps: ServiceDeps, visitor_id: str, case_id: str, mode: Mode) -> Session:
    try:
        loaded = load_case(case_id, deps.cases_dir)
    except CaseNotFoundError as exc:
        raise ServiceError("invalid_input", f"Caso inexistente: {case_id}") from exc
    except CaseError as exc:
        raise ServiceError("internal", "Caso indisponível.") from exc
    deps.gate.check(visitor_id)  # quota / kill switch before writing anything
    case = loaded.case
    now = deps.clock()
    session = Session(
        visitor_id=visitor_id,
        session_id=new_session_id(deps.clock),
        case_id=case.case_id,
        case_version=case.version,
        candidate_no=deps.counter.next(case.case_id),
        status="ready",
        persona=case.persona,
        language=case.language,
        mode=mode,
        job_title=loaded.screening.job_title,
        fit_score=loaded.screening.fit_score,
        created_at=now,
        updated_at=now,
    )
    deps.repo.create_session(session)
    return session


def list_sessions(deps: ServiceDeps, visitor_id: str) -> list[Session]:
    return deps.repo.list_sessions(visitor_id)


def get_session(deps: ServiceDeps, visitor_id: str, session_id: str) -> SessionView:
    with _session_lookup():
        session = deps.repo.get_session(visitor_id, session_id)
        if session.status == "ready" and session.case_id:
            loaded = load_case(session.case_id, deps.cases_dir)
            return SessionView(session=session, case=loaded.case, screening=loaded.screening)
        if session.status == "in_progress":
            turns = deps.repo.list_turns(visitor_id, session_id)
            return SessionView(session=session, turns=[to_public(t) for t in turns])
    return SessionView(session=session)


def delete_session(deps: ServiceDeps, visitor_id: str, session_id: str) -> None:
    with _session_lookup():
        deps.repo.delete_session(visitor_id, session_id)
    deps.reports.delete(session_id)


def rebuild_state(session: Session, plan: InterviewPlan, turns: list[Turn]) -> InterviewState:
    """The service keeps no state: rebuild it from the session row, the turns and the plan."""
    ids = [question.id for question in plan.questions]
    if session.started_at is None or session.current_question_id not in ids:
        raise ServiceError("internal", "Estado da entrevista inconsistente.")
    return InterviewState(
        session_id=session.session_id,
        plan=plan,
        current_index=ids.index(session.current_question_id),
        follow_ups_used=session.follow_ups_used,
        turn_count=session.turn_count,
        started_at=session.started_at,
        turns=turns,
    )


def _load_plan(deps: ServiceDeps, session: Session) -> InterviewPlan:
    try:
        return load_case(session.case_id or "", deps.cases_dir).plan
    except CaseError as exc:
        raise ServiceError("internal", "Caso indisponível.") from exc


def _update(
    deps: ServiceDeps, session: Session, expected: SessionStatus, changes: dict[str, Any]
) -> None:
    """Update with a status guard; a concurrent change means the status is no longer valid."""
    try:
        deps.repo.update_session(
            session.visitor_id, session.session_id, expected_status=expected, changes=changes
        )
    except SessionConflictError as exc:
        raise ServiceError("invalid_state", "A sessão mudou de estado.") from exc


def start_interview(deps: ServiceDeps, visitor_id: str, session_id: str) -> PublicTurn:
    with _session_lookup():
        session = deps.repo.get_session(visitor_id, session_id)
    if session.status != "ready":
        raise ServiceError("invalid_state", "A entrevista só começa em uma sessão pronta.")
    plan = _load_plan(deps, session)
    state, turn = start(session_id, plan, writer=deps.writer_for(session.persona), clock=deps.clock)
    deps.repo.put_turn(visitor_id, turn)
    _update(
        deps,
        session,
        "ready",
        {
            "status": "in_progress",
            "started_at": state.started_at,
            "current_question_id": turn.question_id,
            "follow_ups_used": state.follow_ups_used,
            "turn_count": state.turn_count,
        },
    )
    return to_public(turn)


def _check_answer_allowed(deps: ServiceDeps, session: Session, text: str) -> None:
    """State, then input, then session limits; nothing is written on any refusal."""
    if session.status != "in_progress":
        raise ServiceError("invalid_state", "A entrevista não está em andamento.")
    if not text.strip() or len(text) > DEFAULT_LIMITS.max_answer_chars:
        raise ServiceError(
            "invalid_input",
            f"A resposta deve ter de 1 a {DEFAULT_LIMITS.max_answer_chars} caracteres.",
        )
    elapsed = deps.clock() - (session.started_at or deps.clock())
    if session.turn_count >= DEFAULT_LIMITS.max_turns or elapsed >= timedelta(
        minutes=SESSION_MAX_MINUTES
    ):
        raise ServiceError("session_limit", "A entrevista atingiu o limite da sessão.")


def send_answer(
    deps: ServiceDeps, visitor_id: str, session_id: str, answer_text: str
) -> AnswerResult:
    with _session_lookup():
        session = deps.repo.get_session(visitor_id, session_id)
    _check_answer_allowed(deps, session, answer_text)
    plan = _load_plan(deps, session)
    state = rebuild_state(session, plan, deps.repo.list_turns(visitor_id, session_id))
    try:
        step = answer(
            state,
            answer_text,
            decider=deps.decider,
            writer=deps.writer_for(session.persona),
            scorer=deps.scorer,
            clock=deps.clock,
        )
    except InterviewError as exc:
        raise ServiceError("invalid_input", str(exc)) from exc
    deps.repo.put_turn(visitor_id, step.answered)
    deps.repo.put_turn(visitor_id, step.next_turn)
    if step.state.ended:
        _finish(deps, session, step.state)
        return AnswerResult(ended=True)
    _update(
        deps,
        session,
        "in_progress",
        {
            "current_question_id": step.next_turn.question_id,
            "follow_ups_used": step.state.follow_ups_used,
            "turn_count": step.state.turn_count,
        },
    )
    return AnswerResult(turn=to_public(step.next_turn))


def _finish(deps: ServiceDeps, session: Session, state: InterviewState) -> None:
    """Move to `scoring`, build the report and complete the session.

    On failure the session stays in `scoring` with `error` and the turns are kept.
    """
    _update(
        deps,
        session,
        "in_progress",
        {"status": "scoring", "turn_count": state.turn_count, "ended_at": deps.clock()},
    )
    try:
        result = deps.report(
            state.plan, deps.repo.list_turns(session.visitor_id, session.session_id)
        )
    except (ReportError, LLMInvalidOutputError) as exc:
        message = str(exc) or type(exc).__name__
        _update(deps, session, "scoring", {"error": message})
        raise ServiceError(
            "llm_invalid_output", "Não foi possível gerar o relatório.", retryable=True
        ) from exc
    for turn in result.turns:  # the report scored any missing turn
        deps.repo.put_turn(session.visitor_id, turn)
    deps.reports.save(session.session_id, result.report, result.summary)  # before `completed`
    _update(
        deps,
        session,
        "scoring",
        {
            "status": "completed",
            "overall_score": result.report.overall_score,
            "competency_scores": {c.competency: c.score for c in result.report.competencies},
            "headline": result.summary.headline,
            "error": None,
        },
    )


def end_interview(deps: ServiceDeps, visitor_id: str, session_id: str) -> dict[str, str]:
    with _session_lookup():
        session = deps.repo.get_session(visitor_id, session_id)
    if session.status != "in_progress":
        raise ServiceError("invalid_state", "A entrevista não está em andamento.")
    plan = _load_plan(deps, session)
    state = rebuild_state(session, plan, deps.repo.list_turns(visitor_id, session_id))
    ended, farewell = close_interview(
        state, "visitor", writer=deps.writer_for(session.persona), clock=deps.clock
    )
    deps.repo.put_turn(visitor_id, farewell)
    _finish(deps, session, ended)
    return {"status": "scoring"}


def get_report(deps: ServiceDeps, visitor_id: str, session_id: str) -> ReportView:
    with _session_lookup():
        session = deps.repo.get_session(visitor_id, session_id)
        if session.status != "completed":
            raise ServiceError("invalid_state", "O relatório ainda não está pronto.")
        report, _ = deps.reports.load(session_id)
    turns = deps.repo.list_turns(visitor_id, session_id)
    completed = deps.repo.list_completed(session.case_id) if session.case_id else []
    above = is_above_average(session.overall_score, case_average(completed))
    return ReportView(report=report, turns=turns, is_above_case_avg=above)


def list_recruiter_candidates(deps: ServiceDeps, case_id: str | None = None) -> RecruiterList:
    case_ids = [c.case_id for c in load_cases(deps.cases_dir) if case_id in (None, c.case_id)]
    stats: list[CaseStats] = []
    rows: list[RecruiterCandidateRow] = []
    for cid in case_ids:
        completed = deps.repo.list_completed(cid)  # GSI `by_case` on DynamoDB
        stats.append(case_stats(cid, completed))
        rows.extend(above_average_rows(completed))
    return RecruiterList(stats=stats, candidates=sort_rows(rows))


def get_recruiter_candidate(deps: ServiceDeps, session_id: str) -> RecruiterCandidate:
    completed = deps.repo.list_completed()
    session = next((s for s in completed if s.session_id == session_id), None)
    if session is None:
        raise ServiceError("not_found", "Candidato não encontrado.")
    same_case = deps.repo.list_completed(session.case_id) if session.case_id else []
    with _session_lookup():
        report, summary = deps.reports.load(session_id)
        turns = deps.repo.list_turns(session.visitor_id, session_id)
    return RecruiterCandidate(
        row=build_row(session, case_average(same_case)), summary=summary, report=report, turns=turns
    )
