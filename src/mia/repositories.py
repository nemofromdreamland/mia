"""Repositories: interfaces + in-memory implementations (DynamoDB/S3 come later).

Every operation is keyed by (visitor_id, session_id), like the `mia-sessions` table:
a visitor who does not own the session sees it as missing.
"""

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from mia.schemas import CandidateSummary, Report, Session, SessionStatus, Turn

Clock = Callable[[], datetime]
KEY_FIELDS = frozenset({"visitor_id", "session_id", "created_at", "updated_at"})


class RepositoryError(Exception):
    pass


class SessionNotFoundError(RepositoryError):
    pass


class SessionConflictError(RepositoryError):
    pass


@runtime_checkable
class SessionRepository(Protocol):
    def create_session(self, session: Session) -> None: ...

    def get_session(self, visitor_id: str, session_id: str) -> Session: ...

    def update_session(
        self,
        visitor_id: str,
        session_id: str,
        *,
        expected_status: SessionStatus,
        changes: Mapping[str, Any],
    ) -> Session: ...

    def put_turn(self, visitor_id: str, turn: Turn) -> None: ...

    def list_turns(self, visitor_id: str, session_id: str) -> list[Turn]: ...

    def list_sessions(self, visitor_id: str) -> list[Session]: ...

    def list_completed(self, case_id: str | None = None) -> list[Session]: ...

    def delete_session(self, visitor_id: str, session_id: str) -> None: ...


@runtime_checkable
class ReportStore(Protocol):
    """Report + CandidateSummary of a session (S3 in production)."""

    def save(self, session_id: str, report: Report, summary: CandidateSummary) -> None: ...

    def load(self, session_id: str) -> tuple[Report, CandidateSummary]: ...

    def delete(self, session_id: str) -> None: ...


@runtime_checkable
class CandidateCounter(Protocol):
    """Sequential candidate number per case (atomic in `mia-meta` via `DynamoCandidateCounter`)."""

    def next(self, case_id: str) -> int: ...


def _utc_now() -> datetime:
    return datetime.now(UTC)


class InMemorySessionRepository:
    """Stores deep copies, so callers can never mutate the stored state."""

    def __init__(self, clock: Clock = _utc_now) -> None:
        self._clock = clock
        self._sessions: dict[tuple[str, str], Session] = {}
        self._turns: dict[str, dict[int, Turn]] = {}

    def _require(self, visitor_id: str, session_id: str) -> Session:
        session = self._sessions.get((visitor_id, session_id))
        if session is None:
            raise SessionNotFoundError(f"sessão não encontrada: {session_id}")
        return session

    def create_session(self, session: Session) -> None:
        key = (session.visitor_id, session.session_id)
        if key in self._sessions:
            raise SessionConflictError(f"sessão já existe: {session.session_id}")
        self._sessions[key] = session.model_copy(deep=True)
        self._turns[session.session_id] = {}

    def get_session(self, visitor_id: str, session_id: str) -> Session:
        return self._require(visitor_id, session_id).model_copy(deep=True)

    def update_session(
        self,
        visitor_id: str,
        session_id: str,
        *,
        expected_status: SessionStatus,
        changes: Mapping[str, Any],
    ) -> Session:
        current = self._require(visitor_id, session_id)
        if current.status != expected_status:
            raise SessionConflictError(
                f"status atual {current.status!r}, esperado {expected_status!r}"
            )
        forbidden = KEY_FIELDS & changes.keys()
        if forbidden:
            raise ValueError(f"campos não podem ser alterados: {sorted(forbidden)}")
        data = {**current.model_dump(), **changes, "updated_at": self._clock()}
        updated = Session.model_validate(data)  # raises ValidationError (a ValueError)
        self._sessions[(visitor_id, session_id)] = updated
        return updated.model_copy(deep=True)

    def put_turn(self, visitor_id: str, turn: Turn) -> None:
        self._require(visitor_id, turn.session_id)
        self._turns[turn.session_id][turn.turn_no] = turn.model_copy(deep=True)

    def list_turns(self, visitor_id: str, session_id: str) -> list[Turn]:
        self._require(visitor_id, session_id)
        turns = self._turns[session_id]
        return [turns[no].model_copy(deep=True) for no in sorted(turns)]

    def list_sessions(self, visitor_id: str) -> list[Session]:
        """The visitor's sessions, newest first."""
        own = [s for (vid, _), s in self._sessions.items() if vid == visitor_id]
        own.sort(key=lambda s: (s.created_at, s.session_id), reverse=True)
        return [s.model_copy(deep=True) for s in own]

    def list_completed(self, case_id: str | None = None) -> list[Session]:
        """Completed sessions of every visitor, optionally from a single case."""
        return [
            s.model_copy(deep=True)
            for s in self._sessions.values()
            if s.status == "completed" and (case_id is None or s.case_id == case_id)
        ]

    def delete_session(self, visitor_id: str, session_id: str) -> None:
        self._require(visitor_id, session_id)
        del self._sessions[(visitor_id, session_id)]
        del self._turns[session_id]


class InMemoryReportStore:
    def __init__(self) -> None:
        self._items: dict[str, tuple[Report, CandidateSummary]] = {}

    def save(self, session_id: str, report: Report, summary: CandidateSummary) -> None:
        self._items[session_id] = (report.model_copy(deep=True), summary.model_copy(deep=True))

    def load(self, session_id: str) -> tuple[Report, CandidateSummary]:
        if session_id not in self._items:
            raise SessionNotFoundError(f"relatório não encontrado: {session_id}")
        report, summary = self._items[session_id]
        return report.model_copy(deep=True), summary.model_copy(deep=True)

    def delete(self, session_id: str) -> None:
        self._items.pop(session_id, None)


class InMemoryCandidateCounter:
    def __init__(self) -> None:
        self._values: dict[str, int] = {}

    def next(self, case_id: str) -> int:
        self._values[case_id] = self._values.get(case_id, 0) + 1
        return self._values[case_id]
