from collections.abc import Iterator

import boto3
import pytest
from moto import mock_aws

from mia.repo_s3 import S3ReportStore
from mia.repositories import (
    InMemoryReportStore,
    ReportStore,
    RepositoryError,
    SessionNotFoundError,
)
from mia.schemas import CandidateSummary, Report, SummaryPoint

BUCKET = "mia-data-test"


def _report() -> tuple[Report, CandidateSummary]:
    point = SummaryPoint(point="Clareza", answer_quote="eu usaria")
    summary = CandidateSummary(
        headline="Boa base",
        summary="Resumo.",
        strengths=[point],
        concerns=[point],
        suggested_next_step="advance",
        next_step_reason="Motivo.",
    )
    report = Report(overall_score=3.5, competencies=[], strengths=["a"], improvements=[])
    return report, summary


@pytest.fixture
def s3_client() -> Iterator[object]:
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield client


@pytest.fixture(params=["memory", "s3"])
def store(request: pytest.FixtureRequest, s3_client: object) -> ReportStore:
    if request.param == "memory":
        return InMemoryReportStore()
    return S3ReportStore(s3_client, BUCKET)


def test_contract_save_load_delete(store: ReportStore) -> None:
    assert isinstance(store, ReportStore)
    report, summary = _report()
    store.save("01S", report, summary)
    assert store.load("01S") == (report, summary)
    store.delete("01S")
    with pytest.raises(SessionNotFoundError):
        store.load("01S")
    store.delete("01S")  # deleting twice is harmless


def test_contract_missing_report(store: ReportStore) -> None:
    with pytest.raises(SessionNotFoundError):
        store.load("01NOPE")


def test_contract_overwrite_keeps_last(store: ReportStore) -> None:
    report, summary = _report()
    store.save("01S", report, summary)
    newer = report.model_copy(update={"overall_score": 4.5})
    store.save("01S", newer, summary)
    assert store.load("01S")[0].overall_score == 4.5


def test_s3_keys_follow_backend_schema(s3_client) -> None:  # noqa: ANN001
    store = S3ReportStore(s3_client, BUCKET)
    store.save("01S", *_report())
    listed = s3_client.list_objects_v2(Bucket=BUCKET)["Contents"]
    assert sorted(o["Key"] for o in listed) == [
        "sessions/01S/report.json",
        "sessions/01S/summary.json",
    ]
    body = s3_client.get_object(Bucket=BUCKET, Key="sessions/01S/report.json")["Body"].read()
    assert Report.model_validate_json(body).strengths == ["a"]


def test_s3_other_error_is_repository_error(s3_client) -> None:  # noqa: ANN001
    store = S3ReportStore(s3_client, "bucket-that-does-not-exist")
    with pytest.raises(RepositoryError) as caught:
        store.load("01S")
    assert not isinstance(caught.value, SessionNotFoundError)
    with pytest.raises(RepositoryError):
        store.save("01S", *_report())


def test_from_env_builds_client(s3_client) -> None:  # noqa: ANN001
    store = S3ReportStore.from_env(bucket=BUCKET)
    store.save("01S", *_report())
    assert store.load("01S")[1].headline == "Boa base"
