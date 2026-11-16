"""Single error format: {"error": {"code", "message", "retryable"}}."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from mia.service import ErrorCode, ServiceError

logger = logging.getLogger(__name__)

HTTP_STATUS: dict[ErrorCode, int] = {
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


def error_body(code: ErrorCode, message: str, retryable: bool) -> dict[str, dict[str, object]]:
    return {"error": {"code": code, "message": message, "retryable": retryable}}


def service_error_response(err: ServiceError) -> JSONResponse:
    return JSONResponse(
        status_code=HTTP_STATUS[err.code],
        content=error_body(err.code, err.message, err.retryable),
    )


async def _on_service_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ServiceError)
    return service_error_response(exc)


async def _on_validation_error(request: Request, exc: Exception) -> JSONResponse:
    return service_error_response(ServiceError("invalid_input", "Requisição inválida."))


async def _on_unexpected(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unexpected error")
    return service_error_response(
        ServiceError("internal", "Erro interno. Tente de novo.", retryable=True)
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ServiceError, _on_service_error)
    app.add_exception_handler(RequestValidationError, _on_validation_error)
    app.add_exception_handler(Exception, _on_unexpected)
