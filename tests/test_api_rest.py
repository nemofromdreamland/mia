"""Tests for the REST routes (cases and sessions); the service runs on fakes."""

import pytest
from fakes_service import (
    CASE_ID,
    VISITOR_A,
    VISITOR_B,
    complete_with_score,
    fake_report_result,
    make_deps,
)
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


# ---------- interview, report and recruiter (step 3) ----------


def interview_client() -> tuple[TestClient, ServiceDeps]:
    from mia.schemas import AnswerScore

    deps = make_deps(
        scorer=lambda q, a: AnswerScore(
            score=4, criteria_met=[], evidence_quotes=[], justification="ok"
        )
    ).model_copy(update={"report": fake_report_result})
    return make_client(deps)


def start(client: TestClient, headers: dict[str, str] = H) -> str:
    session_id = create(client, headers)["session_id"]
    response = client.post(f"/sessions/{session_id}/start", headers=headers)
    assert response.status_code == 200
    return session_id


def test_start_returns_first_public_turn() -> None:
    client, _ = interview_client()
    session_id = create(client)["session_id"]
    response = client.post(f"/sessions/{session_id}/start", headers=H)
    assert response.status_code == 200
    body = response.json()
    assert body["turn_no"] == 1
    assert body["interviewer_text"]
    assert not {"score", "decision", "is_follow_up"} & set(body)


def test_happy_path_until_report_with_above_average_flag() -> None:
    client, deps = interview_client()
    for score in (1.0, 2.0):  # two earlier completed sessions of the case
        complete_with_score(deps, VISITOR_B, score)
    session_id = start(client)
    answer = client.post(f"/sessions/{session_id}/turns", json={"answer_text": "olá"}, headers=H)
    assert answer.status_code == 200
    assert answer.json()["ended"] is False
    end = client.post(f"/sessions/{session_id}/end", headers=H)
    assert end.status_code == 200
    assert end.json() == {"status": "scoring"}
    report = client.get(f"/sessions/{session_id}/report", headers=H)
    assert report.status_code == 200
    body = report.json()
    assert body["report"]["overall_score"] == 4.0
    assert body["is_above_case_avg"] is True
    assert body["turns"]


def test_get_session_in_progress_hides_scoring_fields() -> None:
    client, _ = interview_client()
    session_id = start(client)
    client.post(f"/sessions/{session_id}/turns", json={"answer_text": "olá"}, headers=H)
    turns = client.get(f"/sessions/{session_id}", headers=H).json()["turns"]
    assert turns
    for turn in turns:
        assert not {"score", "decision", "is_follow_up"} & set(turn)


def test_turns_in_ready_is_invalid_state() -> None:
    client, _ = interview_client()
    session_id = create(client)["session_id"]
    response = client.post(f"/sessions/{session_id}/turns", json={"answer_text": "x"}, headers=H)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_state"


def test_turn_limit_is_session_limit() -> None:
    client, deps = interview_client()
    session_id = start(client)
    deps.repo.update_session(
        VISITOR_A, session_id, expected_status="in_progress", changes={"turn_count": 30}
    )
    response = client.post(f"/sessions/{session_id}/turns", json={"answer_text": "x"}, headers=H)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "session_limit"


@pytest.mark.parametrize("payload", [{}, {"answer_text": 5}])
def test_answer_body_invalid_is_invalid_input(payload) -> None:
    client, _ = interview_client()
    session_id = start(client)
    response = client.post(f"/sessions/{session_id}/turns", json=payload, headers=H)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_input"


def test_report_failure_is_502_retryable() -> None:
    from mia.report_graph import ReportError

    def failing(plan, turns):
        raise ReportError("boom")

    client, deps = interview_client()
    client.app.state.deps = deps.model_copy(update={"report": failing})
    session_id = start(client)
    response = client.post(f"/sessions/{session_id}/end", headers=H)
    assert response.status_code == 502
    error = response.json()["error"]
    assert error["code"] == "llm_invalid_output"
    assert error["retryable"] is True


def test_unexpected_exception_is_generic_500() -> None:
    def broken(plan, turns):
        raise RuntimeError("segredo")

    client, deps = interview_client()
    client.app.state.deps = deps.model_copy(update={"report": broken})
    session_id = start(client)
    response = client.post(f"/sessions/{session_id}/end", headers=H)
    assert response.status_code == 500
    assert "segredo" not in response.text
    assert response.json()["error"]["code"] == "internal"


def test_report_before_completed_is_invalid_state() -> None:
    client, _ = interview_client()
    session_id = start(client)
    response = client.get(f"/sessions/{session_id}/report", headers=H)
    assert response.status_code == 409


@pytest.mark.parametrize(
    ("method", "suffix"),
    [("post", "start"), ("post", "turns"), ("post", "end"), ("get", "report")],
)
def test_interview_routes_need_visitor_header(method, suffix) -> None:
    client, _ = interview_client()
    kwargs = {"json": {"answer_text": "x"}} if suffix == "turns" else {}
    response = getattr(client, method)(f"/sessions/abc/{suffix}", **kwargs)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_input"


def test_interview_routes_of_other_visitor_are_not_found() -> None:
    client, _ = interview_client()
    session_id = start(client)
    for method, suffix in [("post", "start"), ("post", "end"), ("get", "report")]:
        response = getattr(client, method)(f"/sessions/{session_id}/{suffix}", headers=OTHER)
        assert response.status_code == 404


def test_recruiter_list_and_detail_have_no_visitor_id() -> None:
    client, deps = interview_client()
    ids = [complete_with_score(deps, VISITOR_A, score) for score in (1.0, 2.0, 5.0)]
    listing = client.get("/recruiter/candidates")  # no header needed
    assert listing.status_code == 200
    assert "visitor_id" not in listing.text
    rows = listing.json()["candidates"]
    assert [r["session_id"] for r in rows] == [ids[2]]
    detail = client.get(f"/recruiter/candidates/{ids[2]}")
    assert detail.status_code == 200
    assert "visitor_id" not in detail.text
    assert detail.json()["summary"]["headline"] == "Boa entrevista"


def test_recruiter_filters_by_case_and_unknown_candidate_is_404() -> None:
    client, deps = interview_client()
    complete_with_score(deps, VISITOR_A, 4.0)
    other_case = client.get("/recruiter/candidates", params={"case_id": "no-such-case"})
    assert other_case.status_code == 200
    assert other_case.json()["candidates"] == []
    missing = client.get("/recruiter/candidates/nope")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"
