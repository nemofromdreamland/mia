"""Session repositories: interface + in-memory implementation (DynamoDB comes later).

Every operation is keyed by (visitor_id, session_id), like the `mia-sessions` table:
a visitor who does not own the session sees it as missing.
"""

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from mia.schemas import Session, SessionStatus, Turn

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
