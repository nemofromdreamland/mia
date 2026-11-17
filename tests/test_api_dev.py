"""Local dev server: in-memory wiring, no model call to list cases or create a session."""

from fastapi.testclient import TestClient

from mia.api import dev
from mia.cases import CASES_DIR
from mia.quotas import QuotaGate

VISITOR = "11111111-1111-4111-8111-111111111111"


def test_build_dev_deps_uses_in_memory_gate_and_cases() -> None:
    deps = dev.build_dev_deps()
    assert isinstance(deps.gate, QuotaGate)
    assert deps.cases_dir == CASES_DIR


def test_dev_app_lists_cases_and_creates_a_session(monkeypatch) -> None:
    def no_model(*args, **kwargs):
        raise AssertionError("model must not be called")

    monkeypatch.setattr("mia.llm.run_prompt", no_model, raising=False)
    client = TestClient(dev.build_app())
    headers = {"X-Visitor-Id": VISITOR}

    assert client.get("/ping").json() == {"status": "Healthy"}
    cases = client.get("/cases", headers=headers).json()
    assert len(cases) == 5

    created = client.post(
        "/sessions", json={"case_id": cases[0]["case_id"], "mode": "text"}, headers=headers
    )
    assert created.status_code == 201
    assert created.json()["status"] == "ready"
    assert len(client.get("/sessions", headers=headers).json()) == 1


def test_module_exposes_an_app() -> None:
    assert dev.app.title == "MIA"
