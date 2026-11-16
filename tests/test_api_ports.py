"""Same scenarios through both entrances (REST and /invocations): same status, same body."""

from collections.abc import Callable
from typing import Any

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
from httpx import Response

from mia.api import create_app
from mia.schemas import AnswerScore
from mia.service import ServiceDeps, ServiceError

Call = Callable[..., Response]


class Port:
    """One entrance, exposed as `call(action, visitor_id, session_id, **payload)`."""

    def __init__(self, name: str, client: TestClient) -> None:
        self.name = name
        self.client = client

    def __call__(
        self, action: str, visitor: str | None = VISITOR_A, session: str | None = None, **payload
    ) -> Response:
        if self.name == "invocations":
            body = {"action": action, "visitor_id": visitor, "session_id": session}
            return self.client.post("/invocations", json={**body, "payload": payload})
        return self._rest(action, visitor, session, payload)

    def _rest(
        self, action: str, visitor: str | None, session: str | None, payload: dict
    ) -> Response:
        headers = {"X-Visitor-Id": visitor} if visitor else {}
        sid = f"/sessions/{session}"
        c = self.client
        routes: dict[str, Callable[[], Response]] = {
            "list_cases": lambda: c.get("/cases"),
            "create_session": lambda: c.post("/sessions", json=payload, headers=headers),
            "list_sessions": lambda: c.get("/sessions", headers=headers),
            "get_session": lambda: c.get(sid, headers=headers),
            "start_interview": lambda: c.post(f"{sid}/start", headers=headers),
            "send_answer": lambda: c.post(f"{sid}/turns", json=payload, headers=headers),
            "end_interview": lambda: c.post(f"{sid}/end", headers=headers),
            "get_report": lambda: c.get(f"{sid}/report", headers=headers),
            "delete_session": lambda: c.delete(sid, headers=headers),
            "list_recruiter_candidates": lambda: c.get("/recruiter/candidates", params=payload),
            "get_recruiter_candidate": lambda: c.get(f"/recruiter/candidates/{session}"),
        }
        return routes[action]()


def build_deps(**overrides: Any) -> ServiceDeps:
    deps = make_deps(
        scorer=lambda q, a: AnswerScore(
            score=4, criteria_met=[], evidence_quotes=[], justification="ok"
        ),
        **overrides.pop("make", {}),
    )
    return deps.model_copy(update={"report": fake_report_result, **overrides})


@pytest.fixture(params=["rest", "invocations"])
def port(request) -> Port:
    return Port(request.param, TestClient(create_app(build_deps()), raise_server_exceptions=False))


def deps_of(port: Port) -> ServiceDeps:
    return port.client.app.state.deps


def started(port: Port) -> str:
    sid = port("create_session", case_id=CASE_ID, mode="text").json()["session_id"]
    assert port("start_interview", session=sid).status_code == 200
    return sid


def test_ping(port) -> None:
    response = port.client.get("/ping")
    assert (response.status_code, response.json()) == (200, {"status": "Healthy"})


def test_cases_without_visitor(port) -> None:
    response = port("list_cases", visitor=None)
    assert response.status_code == 200
    assert len(response.json()) == 5


def test_create_session(port) -> None:
    response = port("create_session", case_id=CASE_ID, mode="text")
    assert response.status_code == 201
    assert response.json()["status"] == "ready"


def test_visitor_id_in_payload_is_ignored(port) -> None:
    response = port("create_session", case_id=CASE_ID, mode="text", visitor_id="outro")
    assert response.status_code == 201
    saved = deps_of(port).repo.get_session(VISITOR_A, response.json()["session_id"])
    assert saved.visitor_id == VISITOR_A


@pytest.mark.parametrize("visitor", [None, "abc"])
def test_missing_or_invalid_visitor(port, visitor) -> None:
    response = port("list_sessions", visitor=visitor)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_input"


def test_unknown_case_and_invalid_mode(port) -> None:
    for payload in ({"case_id": "x", "mode": "text"}, {"case_id": CASE_ID, "mode": "video"}):
        response = port("create_session", **payload)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_input"


def test_other_visitor_gets_not_found(port) -> None:
    sid = port("create_session", case_id=CASE_ID, mode="text").json()["session_id"]
    response = port("get_session", visitor=VISITOR_B, session=sid)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_wrong_state_is_409(port) -> None:
    sid = port("create_session", case_id=CASE_ID, mode="text").json()["session_id"]
    response = port("send_answer", session=sid, answer_text="x")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_state"


def test_turn_limit_is_session_limit(port) -> None:
    sid = started(port)
    deps_of(port).repo.update_session(
        VISITOR_A, sid, expected_status="in_progress", changes={"turn_count": 30}
    )
    response = port("send_answer", session=sid, answer_text="x")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "session_limit"


@pytest.mark.parametrize(("code", "status"), [("quota_exceeded", 429), ("demo_paused", 503)])
def test_gate_refusal(code, status, port) -> None:
    deps = build_deps(make={"gate_error": ServiceError(code, "no")})
    port.client.app.state.deps = deps
    response = port("create_session", case_id=CASE_ID, mode="text")
    assert response.status_code == status
    assert response.json()["error"]["code"] == code


def test_report_failure_is_502_and_unexpected_is_500(port) -> None:
    from mia.report_graph import ReportError

    def invalid(plan, turns):
        raise ReportError("boom")

    def broken(plan, turns):
        raise RuntimeError("segredo")

    for report, status, code in ((invalid, 502, "llm_invalid_output"), (broken, 500, "internal")):
        sid = started(port)
        port.client.app.state.deps = deps_of(port).model_copy(update={"report": report})
        response = port("end_interview", session=sid)
        assert response.status_code == status
        assert response.json()["error"]["code"] == code
        assert "segredo" not in response.text


def test_in_progress_session_hides_scoring_fields(port) -> None:
    sid = started(port)
    port("send_answer", session=sid, answer_text="olá")
    turns = port("get_session", session=sid).json()["turns"]
    assert turns
    for turn in turns:
        assert not {"score", "decision", "is_follow_up"} & set(turn)


def test_happy_path_until_report(port) -> None:
    for score in (1.0, 2.0):
        complete_with_score(deps_of(port), VISITOR_B, score)
    sid = started(port)
    answer = port("send_answer", session=sid, answer_text="olá")
    assert answer.status_code == 200 and answer.json()["ended"] is False
    end = port("end_interview", session=sid)
    assert (end.status_code, end.json()) == (200, {"status": "scoring"})
    report = port("get_report", session=sid)
    assert report.status_code == 200
    assert report.json()["is_above_case_avg"] is True


def test_delete_is_204_without_body(port) -> None:
    sid = port("create_session", case_id=CASE_ID, mode="text").json()["session_id"]
    response = port("delete_session", session=sid)
    assert response.status_code == 204
    assert response.content == b""


def test_recruiter_has_no_visitor_id(port) -> None:
    ids = [complete_with_score(deps_of(port), VISITOR_A, s) for s in (1.0, 2.0, 5.0)]
    listing = port("list_recruiter_candidates", visitor=None)
    detail = port("get_recruiter_candidate", visitor=None, session=ids[2])
    assert listing.status_code == detail.status_code == 200
    assert "visitor_id" not in listing.text + detail.text
    assert [r["session_id"] for r in listing.json()["candidates"]] == [ids[2]]


def test_both_ports_return_identical_responses() -> None:
    """Run one scenario on each port and compare status and body, ignoring generated ids."""
    results: dict[str, list[tuple[int, Any]]] = {}
    for name in ("rest", "invocations"):
        p = Port(name, TestClient(create_app(build_deps()), raise_server_exceptions=False))
        out = []
        calls = (
            ("list_cases", {"visitor": None}),
            ("list_sessions", {}),
            ("get_session", {"session": "nope"}),
            ("create_session", {"case_id": "x", "mode": "text"}),
            ("send_answer", {"session": "nope", "answer_text": "x"}),
        )
        for action, kwargs in calls:
            r = p(action, **kwargs)
            out.append((r.status_code, r.json()))
        results[name] = out
    assert results["rest"] == results["invocations"]
