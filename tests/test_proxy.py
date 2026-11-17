"""Lambda proxy: API Gateway HTTP API event (payload 2.0) -> AgentCore `/invocations` body."""

import base64
import json
from typing import Any

import pytest

from proxy.handler import (
    ProxyError,
    build_invocation,
    match_route,
    parse_visitor_id,
    runtime_session_id,
)

VISITOR = "3f8b2c1e-7d4a-4f6b-9a2e-1c5d8e9f0a7b"
SID = "01JD3Y7K2M4N8P0Q6R5S1T9V3W"


def event(
    method: str,
    path: str,
    body: Any = None,
    *,
    visitor: str | None = VISITOR,
    query: dict[str, str] | None = None,
    raw_body: str | None = None,
    b64: bool = False,
) -> dict[str, Any]:
    headers = {"content-type": "application/json"}
    if visitor is not None:
        headers["x-visitor-id"] = visitor
    text = raw_body if raw_body is not None else (None if body is None else json.dumps(body))
    if text is not None and b64:
        text = base64.b64encode(text.encode()).decode()
    result: dict[str, Any] = {
        "version": "2.0",
        "rawPath": path,
        "headers": headers,
        "requestContext": {"http": {"method": method, "path": path}},
        "isBase64Encoded": b64,
    }
    if text is not None:
        result["body"] = text
    if query is not None:
        result["queryStringParameters"] = query
    return result


@pytest.mark.parametrize(
    ("method", "path", "expected"),
    [
        ("GET", "/cases", ("list_cases", None)),
        ("POST", "/sessions", ("create_session", None)),
        ("GET", "/sessions", ("list_sessions", None)),
        ("GET", f"/sessions/{SID}", ("get_session", SID)),
        ("POST", f"/sessions/{SID}/start", ("start_interview", SID)),
        ("POST", f"/sessions/{SID}/turns", ("send_answer", SID)),
        ("POST", f"/sessions/{SID}/end", ("end_interview", SID)),
        ("GET", f"/sessions/{SID}/report", ("get_report", SID)),
        ("DELETE", f"/sessions/{SID}", ("delete_session", SID)),
        ("GET", "/recruiter/candidates", ("list_recruiter_candidates", None)),
        ("GET", f"/recruiter/candidates/{SID}", ("get_recruiter_candidate", SID)),
    ],
)
def test_route_table(method: str, path: str, expected: tuple[str, str | None]) -> None:
    assert match_route(method, path) == expected


@pytest.mark.parametrize(
    ("method", "path"),
    [("GET", "/admin"), ("PUT", "/sessions"), ("GET", f"/sessions/{SID}/x"), ("GET", "/sessions/")],
)
def test_unknown_routes(method: str, path: str) -> None:
    assert match_route(method, path) is None


@pytest.mark.parametrize(
    ("value", "ok"),
    [
        (VISITOR, True),
        (None, False),
        ("", False),
        ("not-a-uuid", False),
        (VISITOR.upper(), False),  # canonical lowercase only, like api/visitor.py
        ("3f8b2c1e-7d4a-1f6b-9a2e-1c5d8e9f0a7b", False),  # version 1
    ],
)
def test_parse_visitor_id(value: str | None, ok: bool) -> None:
    assert (parse_visitor_id(value) == VISITOR) is ok


def test_send_answer_body_never_carries_browser_visitor_id() -> None:
    body = {"answer_text": "Eu usaria um reranker.", "visitor_id": "hack"}
    invocation = build_invocation(event("POST", f"/sessions/{SID}/turns", body))
    assert invocation == {
        "action": "send_answer",
        "visitor_id": VISITOR,
        "session_id": SID,
        "payload": {"answer_text": "Eu usaria um reranker."},
    }


def test_create_session_payload() -> None:
    body = {"case_id": "prompt-engineer-jr", "mode": "text"}
    invocation = build_invocation(event("POST", "/sessions", body))
    assert invocation == {"action": "create_session", "visitor_id": VISITOR, "payload": body}


def test_session_routes_without_body_send_empty_payload() -> None:
    invocation = build_invocation(event("POST", f"/sessions/{SID}/start"))
    assert invocation == {
        "action": "start_interview",
        "visitor_id": VISITOR,
        "session_id": SID,
        "payload": {},
    }


def test_public_routes_omit_visitor() -> None:
    assert build_invocation(event("GET", "/cases")) == {"action": "list_cases", "payload": {}}
    detail = build_invocation(event("GET", f"/recruiter/candidates/{SID}"))
    assert detail == {"action": "get_recruiter_candidate", "session_id": SID, "payload": {}}


def test_recruiter_case_filter_goes_to_payload() -> None:
    with_filter = event("GET", "/recruiter/candidates", query={"case_id": "data-analyst-pleno"})
    assert build_invocation(with_filter)["payload"] == {"case_id": "data-analyst-pleno"}
    assert build_invocation(event("GET", "/recruiter/candidates"))["payload"] == {}


def test_base64_body_is_decoded() -> None:
    invocation = build_invocation(event("POST", "/sessions", {"case_id": "x"}, b64=True))
    assert invocation["payload"] == {"case_id": "x"}


@pytest.mark.parametrize("visitor", [None, "bad", VISITOR.upper()])
def test_invalid_visitor_is_invalid_input_on_every_route(visitor: str | None) -> None:
    for method, path in (("GET", "/cases"), ("GET", "/recruiter/candidates"), ("GET", "/sessions")):
        with pytest.raises(ProxyError) as caught:
            build_invocation(event(method, path, visitor=visitor))
        assert caught.value.code == "invalid_input"


def test_unknown_route_is_not_found() -> None:
    with pytest.raises(ProxyError) as caught:
        build_invocation(event("GET", "/admin"))
    assert caught.value.code == "not_found"


@pytest.mark.parametrize("raw", ["{", "[1]", '"text"'])
def test_invalid_body_is_invalid_input(raw: str) -> None:
    with pytest.raises(ProxyError) as caught:
        build_invocation(event("POST", "/sessions", raw_body=raw))
    assert caught.value.code == "invalid_input"


def test_runtime_session_ids_are_stable_and_long_enough() -> None:
    visitor_sid = runtime_session_id(VISITOR)
    public_sid = runtime_session_id(None)
    assert visitor_sid == f"mia-visitor-{VISITOR}"
    assert public_sid.startswith("mia-public-")
    assert public_sid == runtime_session_id(None)
    assert min(len(visitor_sid), len(public_sid)) >= 33
