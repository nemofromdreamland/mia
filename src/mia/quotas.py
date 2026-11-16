"""Demo kill switch and daily quotas, checked before any session is created.

Order (Backend Schema): demo open -> global quota -> visitor quota. `QuotaGate`
decides; a `MetaStore` (table `mia-meta`) only keeps the counters.
"""

from datetime import UTC, datetime, time, timedelta
from typing import Protocol, runtime_checkable

from mia.repositories import Clock
from mia.service import ServiceError

GLOBAL_DAILY_LIMIT = 100
VISITOR_DAILY_LIMIT = 5
QUOTA_TTL_DAYS = 2


@runtime_checkable
class MetaStore(Protocol):
    def is_demo_open(self) -> bool: ...

    def try_increment(self, pk: str, sk: str, limit: int, expires_at: int) -> bool:
        """Add 1 if the counter is below `limit`; False when it is already at the limit."""
        ...

    def decrement(self, pk: str, sk: str) -> None: ...


class InMemoryMetaStore:
    def __init__(self, demo_open: bool = True) -> None:
        self._demo_open = demo_open
        self._counts: dict[tuple[str, str], int] = {}
        self._expires: dict[tuple[str, str], int] = {}

    def set_demo_open(self, value: bool) -> None:
        self._demo_open = value

    def is_demo_open(self) -> bool:
        return self._demo_open

    def try_increment(self, pk: str, sk: str, limit: int, expires_at: int) -> bool:
        key = (pk, sk)
        if self._counts.get(key, 0) >= limit:
            return False
        self._counts[key] = self._counts.get(key, 0) + 1
        self._expires[key] = expires_at
        return True

    def decrement(self, pk: str, sk: str) -> None:
        self._counts[(pk, sk)] = self._counts.get((pk, sk), 0) - 1

    def get_count(self, pk: str, sk: str) -> int:
        return self._counts.get((pk, sk), 0)

    def get_expires_at(self, pk: str, sk: str) -> int | None:
        return self._expires.get((pk, sk))


def global_key() -> str:
    return "quota#global"


def visitor_key(visitor_id: str) -> str:
    return f"quota#visitor#{visitor_id}"


GLOBAL_EXCEEDED_MESSAGE = "A demo atingiu o limite de hoje. Volte amanhã."
VISITOR_EXCEEDED_MESSAGE = "Você já fez 5 simulações hoje. Volte amanhã para fazer mais."
DEMO_PAUSED_MESSAGE = (
    "A demo está pausada no momento. O histórico e a tela do recrutador continuam disponíveis."
)


class QuotaGate:
    def __init__(
        self,
        store: MetaStore,
        clock: Clock,
        global_limit: int = GLOBAL_DAILY_LIMIT,
        visitor_limit: int = VISITOR_DAILY_LIMIT,
    ) -> None:
        self._store = store
        self._clock = clock
        self._global_limit = global_limit
        self._visitor_limit = visitor_limit

    def check(self, visitor_id: str) -> None:
        if not self._store.is_demo_open():
            raise ServiceError("demo_paused", DEMO_PAUSED_MESSAGE)
        day = self._clock().astimezone(UTC).date()
        sk = day.isoformat()
        midnight = datetime.combine(day, time(), tzinfo=UTC)
        expires_at = int((midnight + timedelta(days=QUOTA_TTL_DAYS)).timestamp())
        if not self._store.try_increment(global_key(), sk, self._global_limit, expires_at):
            raise ServiceError("quota_exceeded", GLOBAL_EXCEEDED_MESSAGE)
        if not self._store.try_increment(
            visitor_key(visitor_id), sk, self._visitor_limit, expires_at
        ):
            self._store.decrement(global_key(), sk)  # give the global unit back
            raise ServiceError("quota_exceeded", VISITOR_EXCEEDED_MESSAGE)
