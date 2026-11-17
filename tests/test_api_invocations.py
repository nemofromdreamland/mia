"""Tests for `POST /invocations` envelope validation (action, visitor, session, payload)."""

import pytest
from fakes_service import CASE_ID, VISITOR_A, make_deps
from fastapi.testclient import TestClient

from mia.api import create_app


def client() -> TestClient:
    return TestClient(create_app(make_deps()), raise_server_exceptions=False)


def invoke(body: dict) -> object:
    return client().post("/invocations", json=body)


def assert_invalid_input(response) -> None:
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_input"
    assert response.json()["error"]["retryable"] is False


def test_unknown_action_is_invalid_input() -> None:
    assert_invalid_input(invoke({"action": "drop_table", "visitor_id": VISITOR_A}))


@pytest.mark.parametrize(
    "action", ["get_session", "start_interview", "send_answer", "end_interview", "get_report"]
)
def test_session_actions_need_session_id(action) -> None:
    assert_invalid_input(invoke({"action": action, "visitor_id": VISITOR_A}))


def test_recruiter_detail_needs_session_id() -> None:
    assert_invalid_input(invoke({"action": "get_recruiter_candidate"}))


@pytest.mark.parametrize("visitor", [None, "abc", "c232ab00-9414-11ec-b3c8-9f6bdeced846"])
def test_visitor_actions_need_valid_visitor_id(visitor) -> None:
    assert_invalid_input(invoke({"action": "list_sessions", "visitor_id": visitor}))


@pytest.mark.parametrize("action", ["list_cases", "list_recruiter_candidates"])
def test_public_actions_need_no_visitor_id(action) -> None:
    assert invoke({"action": action}).status_code == 200


@pytest.mark.parametrize(
    "payload",
    [{}, {"case_id": CASE_ID}, {"case_id": CASE_ID, "mode": "video"}],
)
def test_create_session_invalid_payload(payload) -> None:
    body = {"action": "create_session", "visitor_id": VISITOR_A, "payload": payload}
    assert_invalid_input(invoke(body))


def test_send_answer_invalid_payload() -> None:
    body = {"action": "send_answer", "visitor_id": VISITOR_A, "session_id": "s", "payload": {}}
    assert_invalid_input(invoke(body))


def test_recruiter_case_filter_must_be_string() -> None:
    assert_invalid_input(invoke({"action": "list_recruiter_candidates", "payload": {"case_id": 1}}))


def test_envelope_without_action_is_invalid_input() -> None:
    assert_invalid_input(invoke({"visitor_id": VISITOR_A}))


def test_authorize_voice_action() -> None:
    from mia.service import create_session

    deps = make_deps()
    sid = create_session(deps, VISITOR_A, CASE_ID, "voice").session_id
    c = TestClient(create_app(deps), raise_server_exceptions=False)
    ok = c.post(
        "/invocations",
        json={"action": "authorize_voice", "visitor_id": VISITOR_A, "session_id": sid},
    )
    assert ok.status_code == 200 and ok.json() == {"authorized": True}
    text_sid = create_session(deps, VISITOR_A, CASE_ID, "text").session_id
    bad = c.post(
        "/invocations",
        json={"action": "authorize_voice", "visitor_id": VISITOR_A, "session_id": text_sid},
    )
    assert bad.json()["error"]["code"] == "invalid_state"
