"""Lambda proxy: API Gateway HTTP API (payload 2.0) -> AgentCore Runtime `/invocations`.

Validates `X-Visitor-Id`, translates the REST route into the `action` contract
(Backend Schema, "API") and calls `InvokeAgentRuntime` with the Lambda's IAM role
(boto3 signs with SigV4). Standalone on purpose: it does not import `mia`.
"""

import base64
import json
import os
import re
import uuid
from functools import cache
from typing import Any
from urllib.parse import quote, urlencode, urlparse

import boto3
from botocore.auth import SigV4QueryAuth
from botocore.awsrequest import AWSRequest
from botocore.exceptions import BotoCoreError, ClientError

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
        ("POST", f"/sessions/{SESSION}/voice-url", "voice_url"),
        ("GET", f"/sessions/{SESSION}/examples", "get_examples"),
    )
]
# Same set as NO_VISITOR in src/mia/api/invocations.py: the visitor is validated, not forwarded.
PUBLIC_ACTIONS = frozenset({"list_cases", "list_recruiter_candidates", "get_recruiter_candidate"})
BODY_ACTIONS = frozenset({"create_session", "send_answer"})
PUBLIC_RUNTIME_SESSION = "mia-public-recruiter-and-catalogue"
# Backend Schema, "Erros e validação"; an unknown code is treated as `internal`.
STATUS_BY_CODE = {
    "not_found": 404,
    "invalid_input": 422,
    "invalid_state": 409,
    "session_limit": 409,
    "quota_exceeded": 429,
    "demo_paused": 503,
    "llm_invalid_output": 502,
    "provider_unavailable": 503,
    "internal": 500,
}
SUCCESS_STATUS = {"create_session": 201, "delete_session": 204}
JSON_HEADERS = {"content-type": "application/json"}
# Voice (spec 5): the browser gets a SigV4 presigned wss:// URL to the runtime's /ws.
VOICE_URL_EXPIRES = 300  # AgentCore maximum for presigned WebSocket URLs
VISITOR_QUERY_HEADER = "X-Amzn-Bedrock-AgentCore-Runtime-Custom-X-Visitor-Id"
SESSION_QUERY_HEADER = "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id"
INTERNAL_MESSAGE = "Erro interno. Tente de novo."


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


def _response(status: int, body: str) -> dict[str, Any]:
    return {"statusCode": status, "headers": dict(JSON_HEADERS), "body": body}


def _error(code: str, message: str, retryable: bool) -> dict[str, Any]:
    body = {"error": {"code": code, "message": message, "retryable": retryable}}
    return _response(STATUS_BY_CODE[code], json.dumps(body, ensure_ascii=False))


def to_http(action: str, body: bytes) -> dict[str, Any]:
    """Runtime body -> API Gateway response; status from the error code or the action."""
    text = body.decode()
    try:
        parsed = json.loads(text) if text else None
    except ValueError:
        parsed = None
    if isinstance(parsed, dict) and isinstance(parsed.get("error"), dict):
        return _response(STATUS_BY_CODE.get(parsed["error"].get("code"), 500), text)
    status = SUCCESS_STATUS.get(action, 200)
    return _response(status, "" if status == 204 else text)


def build_voice_url(
    arn: str,
    qualifier: str,
    runtime_session: str,
    visitor_id: str,
    credentials: Any,
    region: str,
    expires: int = VOICE_URL_EXPIRES,
) -> str:
    """Presigned wss:// URL to the runtime's /ws. The visitor goes in as a signed custom
    header, so the browser cannot change it without breaking the signature."""
    query = urlencode(
        {
            "qualifier": qualifier,
            VISITOR_QUERY_HEADER: visitor_id,
            SESSION_QUERY_HEADER: runtime_session,
        }
    )
    host = f"bedrock-agentcore.{region}.amazonaws.com"
    url = f"https://{host}/runtimes/{quote(arn, safe='')}/ws?{query}"
    request = AWSRequest(method="GET", url=url, headers={"host": urlparse(url).hostname})
    SigV4QueryAuth(credentials, "bedrock-agentcore", region, expires=expires).add_auth(request)
    return request.url.replace("https://", "wss://", 1)


def _invoke(client: Any, arn: str, qualifier: str, invocation: dict[str, Any]) -> bytes:
    result = client.invoke_agent_runtime(
        agentRuntimeArn=arn,
        qualifier=qualifier,
        runtimeSessionId=runtime_session_id(invocation.get("visitor_id")),
        contentType="application/json",
        accept="application/json",
        payload=json.dumps(invocation).encode(),
    )
    body: bytes = result["response"].read()
    return body


def voice_url(
    invocation: dict[str, Any], client: Any, arn: str, qualifier: str, signer: Any
) -> dict[str, Any]:
    """Authorize in the backend (owner, voice mode, status, kill switch), then sign."""
    check = {**invocation, "action": "authorize_voice"}
    denied = to_http("authorize_voice", _invoke(client, arn, qualifier, check))
    if denied["statusCode"] != 200:
        return denied
    visitor = invocation["visitor_id"]
    url = signer(arn, qualifier, runtime_session_id(visitor), visitor)
    body = json.dumps({"url": url, "expires_in": VOICE_URL_EXPIRES})
    return {
        "statusCode": 200,
        "headers": {**JSON_HEADERS, "cache-control": "no-store"},
        "body": body,
    }


def handle(
    event: dict[str, Any], client: Any, arn: str, qualifier: str, signer: Any = None
) -> dict[str, Any]:
    try:
        invocation = build_invocation(event)
    except ProxyError as error:
        return _error(error.code, error.message, retryable=False)
    try:
        if invocation["action"] == "voice_url":
            return voice_url(invocation, client, arn, qualifier, signer or _signer)
        body = _invoke(client, arn, qualifier, invocation)
    except (BotoCoreError, ClientError, RuntimeError):
        return _error("internal", INTERNAL_MESSAGE, retryable=True)  # never echo ARN/details
    return to_http(invocation["action"], body)


def _signer(arn: str, qualifier: str, runtime_session: str, visitor_id: str) -> str:
    """Sign with the Lambda role's temporary credentials (never keys in code)."""
    session = boto3.Session()
    credentials = session.get_credentials()
    if credentials is None:
        raise RuntimeError("no credentials")
    region = session.region_name or os.environ.get("AWS_REGION", "us-east-1")
    frozen = credentials.get_frozen_credentials()
    return build_voice_url(arn, qualifier, runtime_session, visitor_id, frozen, region)


@cache
def _client() -> Any:
    """One boto3 client per Lambda container (reused across invocations)."""
    return boto3.client("bedrock-agentcore")


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    arn = os.environ["AGENT_RUNTIME_ARN"]
    qualifier = os.environ.get("AGENT_RUNTIME_QUALIFIER", "DEFAULT")
    return handle(event, _client(), arn, qualifier)
