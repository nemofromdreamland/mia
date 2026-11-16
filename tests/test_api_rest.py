"""Tests for the REST routes (cases and sessions); the service runs on fakes."""

import pytest
from fakes_service import CASE_ID, VISITOR_A, VISITOR_B, make_deps
from fastapi.testclient import TestClient

from mia.api import create_app
from mia.service import ServiceDeps, ServiceError

H = {"X-Visitor-Id": VISITOR_A}
OTHER = {"X-Visitor-Id": VISITOR_B}
V1 = "c232ab00-9414-11ec-b3c8-9f6bdeced846"


def make_client(deps: ServiceDeps | None = None) -> tuple[TestClient, ServiceDeps]:
    deps = deps or make_deps()
    return TestClient(create_app(deps), raise_server_exceptions=False), deps


def create(client: TestClient, headers: dict[str, str] = H) -> dict:
    response = client.post("/sessions", json={"case_id": CASE_ID, "mode": "text"}, headers=headers)
    assert response.status_code == 201
    return response.json()


def test_cases_needs_no_header() -> None:
    client, _ = make_client()
    response = client.get("/cases")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 5
    assert CASE_ID in {c["case_id"] for c in body}


def test_create_session_returns_201_ready() -> None:
    client, _ = make_client()
    body = create(client)
    assert body["status"] == "ready"
    assert body["case_id"] == CASE_ID


def test_visitor_id_in_body_is_ignored() -> None:
    client, deps = make_client()
    response = client.post(
        "/sessions",
        json={"case_id": CASE_ID, "mode": "text", "visitor_id": "outro"},
        headers=H,
    )
    assert response.status_code == 201
    saved = deps.repo.get_session(VISITOR_A, response.json()["session_id"])
    assert saved.visitor_id == VISITOR_A


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/sessions"),
        ("post", "/sessions"),
        ("get", "/sessions/abc"),
        ("delete", "/sessions/abc"),
    ],
)
@pytest.mark.parametrize("headers", [{}, {"X-Visitor-Id": "abc"}, {"X-Visitor-Id": V1}])
def test_visitor_routes_reject_missing_or_invalid_header(method, path, headers) -> None:
    client, _ = make_client()
    kwargs = {"json": {"case_id": CASE_ID, "mode": "text"}} if method == "post" else {}
    response = getattr(client, method)(path, headers=headers, **kwargs)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "invalid_input"
    assert error["retryable"] is False


def test_invalid_header_does_not_call_the_service() -> None:
    from fakes_service import Calls

    calls = Calls()
    client, _ = make_client(make_deps(calls=calls))
    client.post("/sessions", json={"case_id": CASE_ID, "mode": "text"})
    assert calls.gate == 0


def test_unknown_case_is_invalid_input() -> None:
    client, _ = make_client()
    response = client.post("/sessions", json={"case_id": "x", "mode": "text"}, headers=H)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_input"


@pytest.mark.parametrize("payload", [{"case_id": CASE_ID, "mode": "video"}, {"mode": "text"}])
def test_invalid_body_uses_single_error_format(payload) -> None:
    client, _ = make_client()
    response = client.post("/sessions", json=payload, headers=H)
    assert response.status_code == 422
    assert set(response.json()) == {"error"}
    assert response.json()["error"]["code"] == "invalid_input"


def test_broken_json_is_invalid_input() -> None:
    client, _ = make_client()
    response = client.post(
        "/sessions", content="{", headers={**H, "Content-Type": "application/json"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_input"


@pytest.mark.parametrize(("code", "status"), [("quota_exceeded", 429), ("demo_paused", 503)])
def test_gate_refusal_maps_to_http(code, status) -> None:
    client, _ = make_client(make_deps(gate_error=ServiceError(code, "no")))
    response = client.post("/sessions", json={"case_id": CASE_ID, "mode": "text"}, headers=H)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code


def test_list_sessions_only_own() -> None:
    client, _ = make_client()
    mine = create(client)
    create(client, OTHER)
    response = client.get("/sessions", headers=H)
    assert response.status_code == 200
    assert [s["session_id"] for s in response.json()] == [mine["session_id"]]


def test_get_session_ready_has_case_and_screening() -> None:
    client, _ = make_client()
    session = create(client)
    response = client.get(f"/sessions/{session['session_id']}", headers=H)
    assert response.status_code == 200
    body = response.json()
    assert body["session"]["session_id"] == session["session_id"]
    assert body["case"] is not None and body["screening"] is not None


def test_get_session_of_other_visitor_is_not_found() -> None:
    client, _ = make_client()
    session = create(client)
    response = client.get(f"/sessions/{session['session_id']}", headers=OTHER)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_delete_session_is_204_without_body() -> None:
    client, _ = make_client()
    session = create(client)
    response = client.delete(f"/sessions/{session['session_id']}", headers=H)
    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"/sessions/{session['session_id']}", headers=H).status_code == 404
