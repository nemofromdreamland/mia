"""Task 3.5: create_session from a ready-made case — fixture copy, no model call, candidate_no."""

from typing import Any

import pytest
from fakes_service import CASE_ID, VISITOR_A, VISITOR_B, make_deps
from fastapi.testclient import TestClient

from mia import llm
from mia.api import create_app
from mia.cases import load_case
from mia.quotas import InMemoryMetaStore, QuotaGate

VISITOR_C = "33333333-3333-4333-8333-333333333333"
OTHER_CASE = "data-analyst-pleno"
WATCHED = ("invoke", "invoke_structured", "build_chat_model", "append_run_record")


@pytest.fixture
def no_llm(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace every model entry point of llm.py with a stub that records and fails."""
    called: list[str] = []
    for name in WATCHED:

        def stub(*args: Any, _name: str = name, **kwargs: Any) -> Any:
            called.append(_name)
            raise AssertionError(f"llm.{_name} must not be called")

        monkeypatch.setattr(llm, name, stub)
    return called


@pytest.fixture
def client() -> TestClient:
    deps = make_deps()
    gate = QuotaGate(InMemoryMetaStore(), deps.clock)
    deps = deps.model_copy(update={"gate": gate})
    return TestClient(create_app(deps), raise_server_exceptions=False)


def _create(client: TestClient, visitor_id: str, case_id: str = CASE_ID) -> Any:
    body = {"case_id": case_id, "mode": "text"}
    return client.post("/sessions", json=body, headers={"X-Visitor-Id": visitor_id})


def test_session_is_ready_with_fixture_fields(client: TestClient, no_llm: list[str]) -> None:
    response = _create(client, VISITOR_A)
    assert response.status_code == 201
    loaded = load_case(CASE_ID)
    session = response.json()
    assert session["status"] == "ready"
    assert session["case_id"] == loaded.case.case_id
    assert session["case_version"] == loaded.case.version
    assert session["persona"] == loaded.case.persona
    assert session["language"] == loaded.case.language
    assert session["job_title"] == loaded.screening.job_title
    assert session["fit_score"] == loaded.screening.fit_score
    assert no_llm == []


def test_invocations_create_makes_no_model_call(client: TestClient, no_llm: list[str]) -> None:
    body = {
        "action": "create_session",
        "visitor_id": VISITOR_A,
        "payload": {"case_id": CASE_ID, "mode": "text"},
    }
    response = client.post("/invocations", json=body)
    assert response.status_code == 201
    assert response.json()["status"] == "ready"
    assert no_llm == []


def test_candidate_no_is_sequential_across_visitors(client: TestClient, no_llm: list[str]) -> None:
    visitors = [VISITOR_A, VISITOR_B, VISITOR_A, VISITOR_C, VISITOR_B]
    numbers = [_create(client, v).json()["candidate_no"] for v in visitors]
    assert numbers == [1, 2, 3, 4, 5]
    assert no_llm == []


def test_each_case_has_its_own_numbering(client: TestClient) -> None:
    first = [_create(client, VISITOR_A).json()["candidate_no"] for _ in range(2)]
    other = _create(client, VISITOR_B, OTHER_CASE).json()["candidate_no"]
    assert first == [1, 2]
    assert other == 1


def test_unknown_case_leaves_no_gap(client: TestClient) -> None:
    assert _create(client, VISITOR_A).json()["candidate_no"] == 1
    refused = _create(client, VISITOR_A, "nao_existe")
    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "invalid_input"
    assert _create(client, VISITOR_A).json()["candidate_no"] == 2


def test_quota_refusal_leaves_no_gap(client: TestClient) -> None:
    for _ in range(5):
        assert _create(client, VISITOR_A).status_code == 201
    refused = _create(client, VISITOR_A)
    assert refused.status_code == 429
    assert _create(client, VISITOR_B).json()["candidate_no"] == 6


def test_ready_session_shows_screening_without_plan(client: TestClient) -> None:
    session_id = _create(client, VISITOR_A).json()["session_id"]
    response = client.get(f"/sessions/{session_id}", headers={"X-Visitor-Id": VISITOR_A})
    assert response.status_code == 200
    view = response.json()
    assert view["screening"] == load_case(CASE_ID).screening.model_dump(mode="json")
    assert "plan" not in response.text
