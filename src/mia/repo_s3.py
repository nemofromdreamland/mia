"""S3 implementation of `ReportStore` (Backend Schema, "S3").

Layout: `sessions/<session_id>/report.json` (Report) and `summary.json` (CandidateSummary).
"""

from typing import Any

import boto3
from botocore.exceptions import ClientError

from mia.repositories import RepositoryError, SessionNotFoundError
from mia.schemas import CandidateSummary, Report

DATA_PREFIX = "sessions"
_MISSING_CODES = {"NoSuchKey", "404"}


def _key(session_id: str, name: str) -> str:
    return f"{DATA_PREFIX}/{session_id}/{name}.json"


class S3ReportStore:
    """`ReportStore` on a private S3 bucket; documents are the Pydantic JSON."""

    def __init__(self, client: Any, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    @classmethod
    def from_env(cls, *, bucket: str, region: str = "us-east-1") -> "S3ReportStore":
        return cls(boto3.client("s3", region_name=region), bucket)

    def save(self, session_id: str, report: Report, summary: CandidateSummary) -> None:
        self._put(_key(session_id, "report"), report.model_dump_json())
        self._put(_key(session_id, "summary"), summary.model_dump_json())

    def load(self, session_id: str) -> tuple[Report, CandidateSummary]:
        report = Report.model_validate_json(self._get(session_id, "report"))
        summary = CandidateSummary.model_validate_json(self._get(session_id, "summary"))
        return report, summary

    def delete(self, session_id: str) -> None:
        objects = [{"Key": _key(session_id, name)} for name in ("report", "summary")]
        try:
            self._client.delete_objects(Bucket=self._bucket, Delete={"Objects": objects})
        except ClientError as error:
            raise RepositoryError(str(error)) from error

    def _put(self, key: str, body: str) -> None:
        try:
            self._client.put_object(
                Bucket=self._bucket, Key=key, Body=body.encode(), ContentType="application/json"
            )
        except ClientError as error:
            raise RepositoryError(str(error)) from error

    def _get(self, session_id: str, name: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=_key(session_id, name))
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") in _MISSING_CODES:
                raise SessionNotFoundError(f"relatório não encontrado: {session_id}") from error
            raise RepositoryError(str(error)) from error
        return response["Body"].read()
