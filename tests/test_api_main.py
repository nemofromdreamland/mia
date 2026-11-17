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
