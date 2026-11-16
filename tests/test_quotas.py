"""QuotaGate rules: kill switch, then global quota, then visitor quota."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from mia.quotas import (
    GLOBAL_DAILY_LIMIT,
    VISITOR_DAILY_LIMIT,
    InMemoryMetaStore,
    MetaStore,
    QuotaGate,
    global_key,
    visitor_key,
)
from mia.service import ServiceError, SessionGate

V1 = "3f8b2c1e-7d4a-4f6b-9a2e-1c5d8e9f0a7b"
V2 = "9c1d2e3f-4a5b-4c6d-8e7f-0a1b2c3d4e5f"
DAY = datetime(2026, 11, 16, 15, 30, tzinfo=UTC)
SK = "2026-11-16"
EXPIRES = int(datetime(2026, 11, 18, tzinfo=UTC).timestamp())


class FakeClock:
    def __init__(self, now: datetime = DAY) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def make_gate(
    store: InMemoryMetaStore | None = None, clock: FakeClock | None = None
) -> tuple[QuotaGate, InMemoryMetaStore]:
    store = store or InMemoryMetaStore()
    return QuotaGate(store, clock or FakeClock()), store


def refused_code(gate: QuotaGate, visitor_id: str) -> str:
    with pytest.raises(ServiceError) as exc:
        gate.check(visitor_id)
    assert exc.value.retryable is False
    return exc.value.code


def test_defaults_and_keys() -> None:
    assert (GLOBAL_DAILY_LIMIT, VISITOR_DAILY_LIMIT) == (100, 5)
    assert global_key() == "quota#global"
    assert visitor_key(V1) == f"quota#visitor#{V1}"


def test_satisfies_protocols() -> None:
    gate, store = make_gate()
    assert isinstance(gate, SessionGate)
    assert isinstance(store, MetaStore)


def test_paused_demo_refuses_without_touching_quotas() -> None:
    gate, store = make_gate(InMemoryMetaStore(demo_open=False))
    assert refused_code(gate, V1) == "demo_paused"
    assert store.get_count(global_key(), SK) == 0
    assert store.get_count(visitor_key(V1), SK) == 0


def test_set_demo_open_toggles() -> None:
    gate, store = make_gate()
    store.set_demo_open(False)
    assert refused_code(gate, V1) == "demo_paused"
    store.set_demo_open(True)
    gate.check(V1)


def test_first_session_counts_both_with_ttl() -> None:
    gate, store = make_gate()
    gate.check(V1)
    assert store.get_count(global_key(), SK) == 1
    assert store.get_count(visitor_key(V1), SK) == 1
    assert store.get_expires_at(global_key(), SK) == EXPIRES
    assert store.get_expires_at(visitor_key(V1), SK) == EXPIRES


def test_sixth_visitor_session_refused_and_global_compensated() -> None:
    gate, store = make_gate()
    for _ in range(5):
        gate.check(V1)
    assert refused_code(gate, V1) == "quota_exceeded"
    assert store.get_count(global_key(), SK) == 5
    assert store.get_count(visitor_key(V1), SK) == 5


def test_global_exhausted_refuses_new_visitor() -> None:
    store = InMemoryMetaStore()
    for _ in range(GLOBAL_DAILY_LIMIT):
        assert store.try_increment(global_key(), SK, GLOBAL_DAILY_LIMIT, EXPIRES)
    gate, _ = make_gate(store)
    assert refused_code(gate, V1) == "quota_exceeded"
    assert store.get_count(visitor_key(V1), SK) == 0
    assert store.get_count(global_key(), SK) == GLOBAL_DAILY_LIMIT


def test_different_visitors_have_separate_quotas() -> None:
    gate, store = make_gate()
    for _ in range(5):
        gate.check(V1)
    gate.check(V2)
    assert store.get_count(global_key(), SK) == 6


def test_new_utc_day_starts_new_counters() -> None:
    clock = FakeClock()
    gate, store = make_gate(clock=clock)
    for _ in range(5):
        gate.check(V1)
    clock.now = DAY + timedelta(days=1)
    gate.check(V1)
    assert store.get_count(visitor_key(V1), "2026-11-17") == 1


def test_day_uses_utc_even_for_other_timezones() -> None:
    late_brt = datetime(2026, 11, 16, 22, 0, tzinfo=timezone(timedelta(hours=-3)))
    gate, store = make_gate(clock=FakeClock(late_brt))
    gate.check(V1)
    assert store.get_count(global_key(), "2026-11-17") == 1


def test_store_increment_stops_at_limit_and_decrement_returns_one() -> None:
    store = InMemoryMetaStore()
    assert [store.try_increment("k", SK, 2, EXPIRES) for _ in range(3)] == [True, True, False]
    store.decrement("k", SK)
    assert store.get_count("k", SK) == 1
