"""Production entry point: storage chosen by MIA_STORAGE (spec 3.9)."""

import boto3
import pytest
from dynamo_tables import create_meta_table, create_tables
from fastapi.testclient import TestClient
from moto import mock_aws

from mia.api import main
from mia.repo_dynamo import DynamoCandidateCounter, DynamoSessionRepository
from mia.repo_s3 import S3ReportStore
from mia.repositories import InMemoryReportStore, InMemorySessionRepository

VISITOR = "11111111-1111-4111-8111-111111111111"


def test_memory_storage_uses_in_memory_repos() -> None:
    deps = main.build_deps({"MIA_STORAGE": "memory"})
    assert isinstance(deps.repo, InMemorySessionRepository)
    assert isinstance(deps.reports, InMemoryReportStore)


def test_aws_is_the_default_and_wires_dynamo_and_s3() -> None:
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        create_tables(dynamodb)
        create_meta_table(dynamodb)
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="mia-data-test")
        deps = main.build_deps({"MIA_DATA_BUCKET": "mia-data-test"})
        assert isinstance(deps.repo, DynamoSessionRepository)
        assert isinstance(deps.counter, DynamoCandidateCounter)
        assert isinstance(deps.reports, S3ReportStore)
        assert deps.gate.check(VISITOR) is None  # quota + kill switch from mia-meta: open


def test_aws_without_bucket_fails_clearly() -> None:
    with pytest.raises(ValueError, match="MIA_DATA_BUCKET"):
        main.build_deps({"MIA_STORAGE": "aws"})


def test_unknown_storage_lists_accepted_values() -> None:
    with pytest.raises(ValueError, match="aws, memory"):
        main.build_deps({"MIA_STORAGE": "disk"})


def test_app_answers_ping_and_invocations_like_the_container() -> None:
    client = TestClient(main.build_app({"MIA_STORAGE": "memory"}))
    assert client.get("/ping").json() == {"status": "Healthy"}
    response = client.post("/invocations", json={"action": "list_cases"})
    assert response.status_code == 200
    assert len(response.json()) == 5


def test_build_app_reads_os_environ_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MIA_STORAGE", "memory")
    assert main.build_app().title == "MIA"


# ---------- 4.7a: AgentCore only accepts HTTP 200 from /invocations ----------

CASE = "software-intern"


def container() -> TestClient:
    return TestClient(main.build_app({"MIA_STORAGE": "memory"}), raise_server_exceptions=False)


def invoke(client: TestClient, action: str, session: str | None = None, **payload) -> object:
    body = {"action": action, "visitor_id": VISITOR, "session_id": session, "payload": payload}
    return client.post("/invocations", json=body)


def test_create_session_is_200_with_the_session_body() -> None:
    response = invoke(container(), "create_session", case_id=CASE, mode="text")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.headers["content-type"] == "application/json"


def test_service_error_is_200_with_the_error_body() -> None:
    response = invoke(container(), "get_session", session="01ABCDEFGHJKMNPQRSTVWXYZ00")
    assert response.status_code == 200
    assert response.json()["error"]["code"] == "not_found"


def test_validation_error_is_200_with_invalid_input() -> None:
    response = container().post("/invocations", json={"action": "drop_table"})
    assert response.status_code == 200
    assert response.json()["error"]["code"] == "invalid_input"


def test_delete_is_200_with_empty_body() -> None:
    client = container()
    session = invoke(client, "create_session", case_id=CASE, mode="text").json()["session_id"]
    response = invoke(client, "delete_session", session=session)
    assert (response.status_code, response.content) == (200, b"")


def test_rest_routes_keep_their_status() -> None:
    response = container().post(
        "/sessions", json={"case_id": CASE, "mode": "text"}, headers={"X-Visitor-Id": VISITOR}
    )
    assert response.status_code == 201


# ---------- 4.7a: visitor limit from the environment ----------


def test_visitor_limit_defaults_to_the_prd_value() -> None:
    assert main.visitor_limit({}) == 5


def test_visitor_limit_from_env() -> None:
    assert main.visitor_limit({"MIA_VISITOR_DAILY_LIMIT": "20"}) == 20


@pytest.mark.parametrize("value", ["0", "-3", "abc", ""])
def test_invalid_visitor_limit_fails_at_startup(value: str) -> None:
    with pytest.raises(ValueError, match="MIA_VISITOR_DAILY_LIMIT"):
        main.visitor_limit({"MIA_VISITOR_DAILY_LIMIT": value})


def test_aws_gate_uses_the_env_limit() -> None:
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        create_tables(dynamodb)
        create_meta_table(dynamodb)
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="mia-data-test")
        env = {"MIA_DATA_BUCKET": "mia-data-test", "MIA_VISITOR_DAILY_LIMIT": "2"}
        gate = main.build_deps(env).gate
        gate.check(VISITOR)
        gate.check(VISITOR)
        with pytest.raises(Exception, match="fez 2 "):
            gate.check(VISITOR)
