"""Lambda proxy: API Gateway HTTP API (payload 2.0) -> AgentCore Runtime `/invocations`.

Validates `X-Visitor-Id`, translates the REST route into the `action` contract
(Backend Schema, "API") and calls `InvokeAgentRuntime` with the Lambda's IAM role
(boto3 signs with SigV4). Standalone on purpose: it does not import `mia`.
"""

import base64
import json
import re
import uuid
from typing import Any

SESSION = r"(?P<sid>[A-Za-z0-9]+)"
ROUTES: list[tuple[str, re.Pattern[str], str]] = [
    (method, re.compile(f"^{pattern}$"), action)
    for method, pattern, action in (
        ("GET", "/cases", "list_cases"),
        ("POST", "/sessions", "create_session"),
        ("GET", "/sessions", "list_sessions"),
        ("GET", f"/sessions/{SESSION}", "get_session"),
        ("POST", f"/sessions/{SESSION}/start", "start_interview"),
        ("POST", f"/sessions/{SESSION}/turns", "send_answer"),
        ("POST", f"/sessions/{SESSION}/end", "end_interview"),
        ("GET", f"/sessions/{SESSION}/report", "get_report"),
        ("DELETE", f"/sessions/{SESSION}", "delete_session"),
        ("GET", "/recruiter/candidates", "list_recruiter_candidates"),
        ("GET", f"/recruiter/candidates/{SESSION}", "get_recruiter_candidate"),
    )
]
# Same set as NO_VISITOR in src/mia/api/invocations.py: the visitor is validated, not forwarded.
PUBLIC_ACTIONS = frozenset({"list_cases", "list_recruiter_candidates", "get_recruiter_candidate"})
BODY_ACTIONS = frozenset({"create_session", "send_answer"})
PUBLIC_RUNTIME_SESSION = "mia-public-recruiter-and-catalogue"


class ProxyError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def parse_visitor_id(value: str | None) -> str | None:
    """Canonical lowercase UUID v4, or None (same rule as `mia.api.visitor`)."""
    try:
        parsed = uuid.UUID(value or "")
    except ValueError:
        return None
    if parsed.version != 4 or str(parsed) != value:
        return None
    return value


def match_route(method: str, path: str) -> tuple[str, str | None] | None:
    for route_method, pattern, action in ROUTES:
        found = pattern.match(path)
        if route_method == method and found:
            return action, found.groupdict().get("sid")
    return None


def _json_body(event: dict[str, Any]) -> dict[str, Any]:
    raw = event.get("body")
    if not raw:
        return {}
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode()
    try:
        body = json.loads(raw)
    except ValueError as error:
        raise ProxyError("invalid_input", "Corpo inválido.") from error
    if not isinstance(body, dict):
        raise ProxyError("invalid_input", "Corpo inválido.")
    body.pop("visitor_id", None)  # the visitor only ever comes from the header
    return body


def _payload(action: str, event: dict[str, Any]) -> dict[str, Any]:
    if action in BODY_ACTIONS:
        return _json_body(event)
    if action == "list_recruiter_candidates":
        case_id = (event.get("queryStringParameters") or {}).get("case_id")
        return {} if case_id is None else {"case_id": case_id}
    return {}


def build_invocation(event: dict[str, Any]) -> dict[str, Any]:
    """The `/invocations` body for an API Gateway event; raises `ProxyError`."""
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    visitor = parse_visitor_id(headers.get("x-visitor-id"))
    if visitor is None:
        raise ProxyError("invalid_input", "X-Visitor-Id ausente ou inválido.")
    http = event.get("requestContext", {}).get("http", {})
    route = match_route(http.get("method", ""), event.get("rawPath") or http.get("path", ""))
    if route is None:
        raise ProxyError("not_found", "Rota não encontrada.")
    action, session_id = route
    invocation: dict[str, Any] = {"action": action}
    if action not in PUBLIC_ACTIONS:
        invocation["visitor_id"] = visitor
    if session_id is not None:
        invocation["session_id"] = session_id
    invocation["payload"] = _payload(action, event)
    return invocation


def runtime_session_id(visitor_id: str | None) -> str:
    """Stable id (>= 33 chars): one runtime session per visitor, one for public routes."""
    return PUBLIC_RUNTIME_SESSION if visitor_id is None else f"mia-visitor-{visitor_id}"
