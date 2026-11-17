"""End-to-end quota tests: real `QuotaGate` + in-memory store behind the HTTP API."""

from fakes_service import CASE_ID, VISITOR_A, VISITOR_B, make_deps
from fastapi.testclient import TestClient

from mia.api import create_app
from mia.quotas import InMemoryMetaStore, QuotaGate

V1 = "c232ab00-9414-11ec-b3c8-9f6bdeced846"
H = {"X-Visitor-Id": VISITOR_A}
BODY = {"case_id": CASE_ID, "mode": "text"}


def make_client(demo_open: bool = True) -> tuple[TestClient, InMemoryMetaStore]:
    deps = make_deps()
    store = InMemoryMetaStore(demo_open=demo_open)
    deps = deps.model_copy(update={"gate": QuotaGate(store, deps.clock)})
    return TestClient(create_app(deps), raise_server_exceptions=False), store


def assert_error(response, status: int, code: str) -> None:
    assert response.status_code == status
    error = response.json()["error"]
    assert error["code"] == code
    assert error["retryable"] is False


def test_header_missing_or_invalid_is_invalid_input() -> None:
    client, _ = make_client()
    for headers in ({}, {"X-Visitor-Id": V1}, {"X-Visitor-Id": "abc"}):
        assert_error(client.post("/sessions", json=BODY, headers=headers), 422, "invalid_input")


def test_body_visitor_id_is_ignored() -> None:
    client, _ = make_client()
    response = client.post("/sessions", json={**BODY, "visitor_id": VISITOR_B}, headers=H)
    assert response.status_code == 201
    assert len(client.get("/sessions", headers=H).json()) == 1
    assert client.get("/sessions", headers={"X-Visitor-Id": VISITOR_B}).json() == []


def test_invocations_payload_visitor_id_is_ignored() -> None:
    client, _ = make_client()
    body = {
        "action": "create_session",
        "visitor_id": VISITOR_A,
        "payload": {**BODY, "visitor_id": VISITOR_B},
    }
    assert client.post("/invocations", json=body).status_code == 201
    assert len(client.get("/sessions", headers=H).json()) == 1
    assert client.get("/sessions", headers={"X-Visitor-Id": VISITOR_B}).json() == []


def test_sixth_session_is_quota_exceeded() -> None:
    client, _ = make_client()
    codes = [client.post("/sessions", json=BODY, headers=H).status_code for _ in range(5)]
    assert codes == [201] * 5
    assert_error(client.post("/sessions", json=BODY, headers=H), 429, "quota_exceeded")
    # another visitor is not affected
    other = {"X-Visitor-Id": VISITOR_B}
    assert client.post("/sessions", json=BODY, headers=other).status_code == 201


def test_paused_demo_rest_and_invocations() -> None:
    client, _ = make_client(demo_open=False)
    assert_error(client.post("/sessions", json=BODY, headers=H), 503, "demo_paused")
    body = {"action": "create_session", "visitor_id": VISITOR_A, "payload": BODY}
    assert_error(client.post("/invocations", json=body), 503, "demo_paused")
    assert client.get("/sessions", headers=H).json() == []
