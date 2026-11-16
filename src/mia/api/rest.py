"""REST routes: thin adapters over `mia.service` (no business rules here)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, TypeAdapter

from mia import service
from mia.api.visitor import visitor_id_header
from mia.schemas import Mode
from mia.service import ServiceDeps

router = APIRouter()

VisitorId = Annotated[str, Depends(visitor_id_header)]


def get_deps(request: Request) -> ServiceDeps:
    deps: ServiceDeps = request.app.state.deps
    return deps


Deps = Annotated[ServiceDeps, Depends(get_deps)]


def build_response(status: int, data: Any = None) -> Response:
    """Single place that turns `(status, model)` into HTTP; `/invocations` reuses it."""
    if data is None:
        return Response(status_code=status)
    body = TypeAdapter(Any).dump_json(data, by_alias=True)
    return Response(content=body, status_code=status, media_type="application/json")


class CreateSessionBody(BaseModel):
    model_config = ConfigDict(extra="ignore")  # a `visitor_id` in the body is dropped

    case_id: str
    mode: Mode


@router.get("/cases")
def list_cases(deps: Deps) -> Response:
    return build_response(200, service.list_cases(deps))


@router.post("/sessions")
def create_session(body: CreateSessionBody, visitor_id: VisitorId, deps: Deps) -> Response:
    session = service.create_session(deps, visitor_id, body.case_id, body.mode)
    return build_response(201, session)


@router.get("/sessions")
def list_sessions(visitor_id: VisitorId, deps: Deps) -> Response:
    return build_response(200, service.list_sessions(deps, visitor_id))


@router.get("/sessions/{session_id}")
def get_session(session_id: str, visitor_id: VisitorId, deps: Deps) -> Response:
    return build_response(200, service.get_session(deps, visitor_id, session_id))


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str, visitor_id: VisitorId, deps: Deps) -> Response:
    service.delete_session(deps, visitor_id, session_id)
    return build_response(204)
