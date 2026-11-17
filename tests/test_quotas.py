"""QuotaGate rules: kill switch, then global quota, then visitor quota."""

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import boto3
import pytest
from botocore.exceptions import ClientError
from dynamo_tables import create_meta_table
from moto import mock_aws

from mia.quotas import (
    GLOBAL_DAILY_LIMIT,
    VISITOR_DAILY_LIMIT,
    InMemoryMetaStore,
    MetaStore,
    QuotaGate,
    global_key,
    visitor_key,
)
from mia.repo_dynamo import DynamoMetaStore
from mia.repositories import RepositoryError
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


# --- MetaStore contract: the same tests run on memory and on DynamoDB (moto) ---


@pytest.fixture
def meta_table(monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    with mock_aws():
        yield create_meta_table(boto3.resource("dynamodb", region_name="us-east-1"))


@pytest.fixture(params=["memory", "dynamo"])
def store_and_setter(
    request: pytest.FixtureRequest,
) -> tuple[MetaStore, Callable[[bool], None]]:
    if request.param == "memory":
        memory = InMemoryMetaStore()
        return memory, memory.set_demo_open
    table = request.getfixturevalue("meta_table")
    return DynamoMetaStore(table), lambda value: table.put_item(
        Item={"pk": "config", "sk": "demo", "open": value}
    )


def test_contract_increment_stops_at_limit_and_decrement_returns_one(
    store_and_setter: tuple[MetaStore, Callable[[bool], None]],
) -> None:
    store, _ = store_and_setter
    assert [store.try_increment("k", SK, 2, EXPIRES) for _ in range(3)] == [True, True, False]
    store.decrement("k", SK)
    assert store.try_increment("k", SK, 2, EXPIRES) is True
    assert store.try_increment("k", SK, 2, EXPIRES) is False


def test_contract_counters_are_independent(
    store_and_setter: tuple[MetaStore, Callable[[bool], None]],
) -> None:
    store, _ = store_and_setter
    assert store.try_increment("a", SK, 1, EXPIRES)
    assert store.try_increment("b", SK, 1, EXPIRES)
    assert store.try_increment("a", "2026-11-17", 1, EXPIRES)
    assert not store.try_increment("a", SK, 1, EXPIRES)


def test_contract_demo_open_by_default_and_follows_config(
    store_and_setter: tuple[MetaStore, Callable[[bool], None]],
) -> None:
    store, set_open = store_and_setter
    assert store.is_demo_open() is True  # P1: missing config means open
    set_open(False)
    assert store.is_demo_open() is False
    set_open(True)
    assert store.is_demo_open() is True


def test_contract_gate_end_to_end(
    store_and_setter: tuple[MetaStore, Callable[[bool], None]],
) -> None:
    store, set_open = store_and_setter
    gate = QuotaGate(store, FakeClock())
    for _ in range(5):
        gate.check(V1)
    assert refused_code(gate, V1) == "quota_exceeded"
    set_open(False)
    assert refused_code(gate, V2) == "demo_paused"


def test_dynamo_increment_writes_count_and_expires_at(meta_table: Any) -> None:
    DynamoMetaStore(meta_table).try_increment("k", SK, 5, EXPIRES)
    item = meta_table.get_item(Key={"pk": "k", "sk": SK})["Item"]
    assert (int(item["count"]), int(item["expires_at"])) == (1, EXPIRES)


def test_dynamo_paused_demo_refuses_through_gate(meta_table: Any) -> None:
    meta_table.put_item(Item={"pk": "config", "sk": "demo", "open": False})
    gate = QuotaGate(DynamoMetaStore(meta_table), FakeClock())
    assert refused_code(gate, V1) == "demo_paused"
    assert "Item" not in meta_table.get_item(Key={"pk": global_key(), "sk": SK})


def test_dynamo_missing_table_becomes_repository_error(meta_table: Any) -> None:
    meta_table.delete()
    store = DynamoMetaStore(meta_table)
    with pytest.raises(RepositoryError):
        store.is_demo_open()
    with pytest.raises(RepositoryError):
        store.try_increment("k", SK, 1, EXPIRES)
    with pytest.raises(RepositoryError):
        store.decrement("k", SK)


def test_dynamo_non_conditional_error_becomes_repository_error() -> None:
    class Broken:
        def update_item(self, **kwargs: Any) -> Any:
            raise ClientError({"Error": {"Code": "ProvisionedThroughputExceeded"}}, "UpdateItem")

    with pytest.raises(RepositoryError):
        DynamoMetaStore(Broken()).try_increment("k", SK, 1, EXPIRES)
