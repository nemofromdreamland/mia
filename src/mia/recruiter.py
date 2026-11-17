"""Recruiter rules (Backend Schema, "Tela do recrutador: regras"), as pure functions.

The service does the I/O (`repo.list_completed(case_id)`, GSI `by_case` on DynamoDB) and
hands the completed sessions of one case to these functions.
"""

from mia.schemas import CaseStats, RecruiterCandidateRow, Session

MIN_SESSIONS_FOR_AVERAGE = 3  # the case average only exists from here on


def case_average(completed: list[Session]) -> float | None:
    """Mean `overall_score` of a case's completed sessions; None with fewer than 3."""
    if len(completed) < MIN_SESSIONS_FOR_AVERAGE:
        return None
    return sum(s.overall_score or 0.0 for s in completed) / len(completed)


def is_above_average(score: float | None, average: float | None) -> bool | None:
    """None without an average; otherwise strictly greater than it."""
    if average is None:
        return None
    return (score or 0.0) > average


def build_row(session: Session, average: float | None) -> RecruiterCandidateRow:
    """Anonymous row: built field by field, so `visitor_id` cannot leak."""
    score = session.overall_score or 0.0
    return RecruiterCandidateRow(
        session_id=session.session_id,
        case_id=session.case_id or "",
        candidate_no=session.candidate_no or 0,
        ended_at=session.ended_at or session.updated_at,
        overall_score=score,
        delta_vs_case_avg=None if average is None else round(score - average, 2),
        headline=session.headline or "",
    )


def case_stats(case_id: str, completed: list[Session]) -> CaseStats:
    average = case_average(completed)
    return CaseStats(
        case_id=case_id,
        completed_sessions=len(completed),
        average_score=None if average is None else round(average, 2),
    )


def sort_rows(rows: list[RecruiterCandidateRow]) -> list[RecruiterCandidateRow]:
    """Largest delta first; ties (and rows without average) by the most recent session."""
    return sorted(
        rows,
        key=lambda r: (r.delta_vs_case_avg is not None, r.delta_vs_case_avg or 0.0, r.ended_at),
        reverse=True,
    )


def above_average_rows(completed: list[Session]) -> list[RecruiterCandidateRow]:
    """Rows of one case: all of them without an average, only those above it otherwise."""
    average = case_average(completed)
    shown = [s for s in completed if is_above_average(s.overall_score, average) is not False]
    return sort_rows([build_row(s, average) for s in shown])
