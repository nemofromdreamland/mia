"""Tests for the API skeleton: /ping, the single error format and X-Visitor-Id parsing."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from test_service import make_deps

from mia.api import create_app
from mia.api.errors import HTTP_STATUS
from mia.api.visitor import parse_visitor_id
from mia.service import ServiceError

V4 = "3f8b2c1e-7d4a-4f6b-9a2e-1c5d8e9f0a7b"
V1 = "c232ab00-9414-11ec-b3c8-9f6bdeced846"


class Body(BaseModel):
    mode: int


def app_with_test_routes() -> FastAPI:
    app = create_app(make_deps())

    @app.get("/boom/{code}")
    def boom(code: str) -> None:
        raise ServiceError(code, f"falhou: {code}", retryable=code == "llm_invalid_output")  # type: ignore[arg-type]

    @app.get("/crash")
    def crash() -> None:
        raise RuntimeError("segredo interno")

    @app.post("/body")
    def body(payload: Body) -> dict[str, int]:
        return {"mode": payload.mode}

    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app_with_test_routes(), raise_server_exceptions=False)


def test_ping_is_healthy(client: TestClient) -> None:
    response = client.get("/ping")
    assert response.status_code == 200
    assert response.json() == {"status": "Healthy"}


@pytest.mark.parametrize(
    ("code", "status"),
    [
        ("not_found", 404),
        ("invalid_input", 422),
        ("invalid_state", 409),
        ("session_limit", 409),
        ("quota_exceeded", 429),
        ("demo_paused", 503),
        ("llm_invalid_output", 502),
        ("provider_unavailable", 503),
        ("internal", 500),
    ],
)
def test_service_error_maps_to_status_and_single_format(
    client: TestClient, code: str, status: int
) -> None:
    response = client.get(f"/boom/{code}")
    assert response.status_code == status
    assert response.json() == {
        "error": {
            "code": code,
            "message": f"falhou: {code}",
            "retryable": code == "llm_invalid_output",
        }
    }


def test_status_table_covers_every_error_code() -> None:
    assert len(HTTP_STATUS) == 9


@pytest.mark.parametrize("raw", ['{"mode": "x"}', "{", "{}"])
def test_validation_error_is_invalid_input_in_single_format(client: TestClient, raw: str) -> None:
    response = client.post("/body", content=raw, headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "invalid_input"
    assert error["retryable"] is False
    assert set(response.json()) == {"error"}


def test_unexpected_exception_is_internal_without_details(client: TestClient) -> None:
    response = client.get("/crash")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal"
    assert response.json()["error"]["retryable"] is True
    assert "segredo" not in response.text


def test_parse_visitor_id_accepts_v4_and_normalizes_case() -> None:
    assert parse_visitor_id(V4.upper()) == V4


@pytest.mark.parametrize("value", [None, "", "abc", V1, V4 + "0"])
def test_parse_visitor_id_rejects_missing_or_not_v4(value: str | None) -> None:
    with pytest.raises(ServiceError) as err:
        parse_visitor_id(value)
    assert err.value.code == "invalid_input"
