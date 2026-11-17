"""`POST /invocations`: dispatch by `action` to the same service operations as REST."""

from collections.abc import Callable
from typing import Any, Literal, get_args

from fastapi import APIRouter, Response
from pydantic import BaseModel, ValidationError

from mia import service
from mia.api.rest import AnswerBody, CreateSessionBody, Deps, build_response
from mia.api.visitor import parse_visitor_id
from mia.service import ServiceDeps, ServiceError

Action = Literal[
    "list_cases",
    "create_session",
    "list_sessions",
    "get_session",
    "start_interview",
    "send_answer",
    "end_interview",
    "get_report",
    "delete_session",
    "list_recruiter_candidates",
    "get_recruiter_candidate",
    "authorize_voice",
]

router = APIRouter()

# Actions that need no visitor (public catalogue and recruiter screens).
NO_VISITOR: frozenset[str] = frozenset(
    {"list_cases", "list_recruiter_candidates", "get_recruiter_candidate"}
)
# Actions that act on one session and therefore need `session_id`.
NEEDS_SESSION: frozenset[str] = frozenset(
    {
        "get_session",
        "start_interview",
        "send_answer",
        "end_interview",
        "get_report",
        "delete_session",
        "get_recruiter_candidate",
        "authorize_voice",
    }
)


class InvocationRequest(BaseModel):
    action: str  # checked against `Action` by hand, so a bad one is `invalid_input`
    visitor_id: str | None = None
    session_id: str | None = None
    payload: dict[str, Any] = {}


def _parse_payload[T: BaseModel](model: type[T], payload: dict[str, Any]) -> T:
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise ServiceError("invalid_input", "Payload inválido.") from exc


def _case_filter(payload: dict[str, Any]) -> str | None:
    case_id = payload.get("case_id")
    if case_id is not None and not isinstance(case_id, str):
        raise ServiceError("invalid_input", "Payload inválido.")
    return case_id


def _run(deps: ServiceDeps, req: InvocationRequest, visitor: str, session: str) -> Response:
    """Call the service for a validated request. `visitor`/`session` are "" when unused."""
    handlers: dict[str, Callable[[], Response]] = {
        "list_cases": lambda: build_response(200, service.list_cases(deps)),
        "create_session": lambda: _create(deps, req, visitor),
        "list_sessions": lambda: build_response(200, service.list_sessions(deps, visitor)),
        "get_session": lambda: build_response(200, service.get_session(deps, visitor, session)),
        "start_interview": lambda: build_response(
            200, service.start_interview(deps, visitor, session)
        ),
        "send_answer": lambda: _answer(deps, req, visitor, session),
        "end_interview": lambda: build_response(200, service.end_interview(deps, visitor, session)),
        "get_report": lambda: build_response(200, service.get_report(deps, visitor, session)),
        "delete_session": lambda: _delete(deps, visitor, session),
        "list_recruiter_candidates": lambda: build_response(
            200, service.list_recruiter_candidates(deps, _case_filter(req.payload))
        ),
        "get_recruiter_candidate": lambda: build_response(
            200, service.get_recruiter_candidate(deps, session)
        ),
        "authorize_voice": lambda: _authorize_voice(deps, visitor, session),
    }
    return handlers[req.action]()


def _create(deps: ServiceDeps, req: InvocationRequest, visitor: str) -> Response:
    body = _parse_payload(CreateSessionBody, req.payload)
    return build_response(201, service.create_session(deps, visitor, body.case_id, body.mode))


def _answer(deps: ServiceDeps, req: InvocationRequest, visitor: str, session: str) -> Response:
    body = _parse_payload(AnswerBody, req.payload)
    return build_response(200, service.send_answer(deps, visitor, session, body.answer_text))


def _authorize_voice(deps: ServiceDeps, visitor: str, session: str) -> Response:
    service.authorize_voice(deps, visitor, session)
    return build_response(200, {"authorized": True})


def _delete(deps: ServiceDeps, visitor: str, session: str) -> Response:
    service.delete_session(deps, visitor, session)
    return build_response(204)


def dispatch(deps: ServiceDeps, req: InvocationRequest) -> Response:
    """Validate the envelope, then run the action; errors go through the shared handlers."""
    if req.action not in get_args(Action):
        raise ServiceError("invalid_input", "Action desconhecida.")
    visitor = "" if req.action in NO_VISITOR else parse_visitor_id(req.visitor_id)
    if req.action in NEEDS_SESSION and not req.session_id:
        raise ServiceError("invalid_input", "session_id é obrigatório para esta action.")
    return _run(deps, req, visitor, req.session_id or "")


@router.post("/invocations")
def invocations(req: InvocationRequest, deps: Deps) -> Response:
    return dispatch(deps, req)
