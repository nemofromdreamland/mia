"""Production entry point (container): `uvicorn --factory mia.api.main:build_app`.

`MIA_STORAGE` picks the storage: `aws` (default; DynamoDB + S3, bucket in `MIA_DATA_BUCKET`,
region in `AWS_REGION`) or `memory` (same wiring as `mia.api.dev`, to run the container
locally without AWS). Credentials never live in the image: the runtime role provides them.
"""

import os
from collections.abc import Mapping

from fastapi import FastAPI

from mia.api.app import create_app
from mia.api.dev import _utc_now, build_dev_deps
from mia.quotas import QuotaGate
from mia.repo_dynamo import DynamoCandidateCounter, DynamoMetaStore, DynamoSessionRepository
from mia.repo_s3 import S3ReportStore
from mia.service import ServiceDeps

STORAGE_VALUES = ("aws", "memory")
DEFAULT_REGION = "us-east-1"


def _aws_deps(env: Mapping[str, str]) -> ServiceDeps:
    bucket = env.get("MIA_DATA_BUCKET")
    if not bucket:
        raise ValueError("MIA_STORAGE=aws requer MIA_DATA_BUCKET (bucket dos relatórios).")
    region = env.get("AWS_REGION", DEFAULT_REGION)
    base = build_dev_deps()  # model wiring (writer, scorer, report) is the same everywhere
    return base.model_copy(
        update={
            "repo": DynamoSessionRepository.from_env(region=region),
            "reports": S3ReportStore.from_env(bucket=bucket, region=region),
            "counter": DynamoCandidateCounter.from_env(region=region),
            "gate": QuotaGate(DynamoMetaStore.from_env(region=region), clock=_utc_now),
        }
    )


def build_deps(env: Mapping[str, str]) -> ServiceDeps:
    storage = env.get("MIA_STORAGE", "aws")
    if storage == "memory":
        return build_dev_deps()
    if storage == "aws":
        return _aws_deps(env)
    raise ValueError(
        f"MIA_STORAGE inválido: {storage!r}. Valores aceitos: {', '.join(STORAGE_VALUES)}."
    )


def build_app(env: Mapping[str, str] | None = None) -> FastAPI:
    return create_app(build_deps(os.environ if env is None else env))
