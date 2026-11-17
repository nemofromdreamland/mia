"""Production entry point (container): `uvicorn --factory mia.api.main:build_app`.

`MIA_STORAGE` picks the storage: `aws` (default; DynamoDB + S3, bucket in `MIA_DATA_BUCKET`,
region in `AWS_REGION`) or `memory` (same wiring as `mia.api.dev`, to run the container
locally without AWS). Credentials never live in the image: the runtime role provides them.
"""

import os
from collections.abc import Awaitable, Callable, Mapping

from fastapi import FastAPI, Request, Response

from mia.api.app import create_app
from mia.api.dev import _utc_now, build_dev_deps
from mia.quotas import VISITOR_DAILY_LIMIT, QuotaGate
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
            "gate": QuotaGate(
                DynamoMetaStore.from_env(region=region),
                clock=_utc_now,
                visitor_limit=visitor_limit(env),
            ),
        }
    )


def visitor_limit(env: Mapping[str, str]) -> int:
    """Sessions per visitor per day: `MIA_VISITOR_DAILY_LIMIT` (integer >= 1), PRD default 5."""
    raw = env.get("MIA_VISITOR_DAILY_LIMIT")
    if raw is None:
        return VISITOR_DAILY_LIMIT
    try:
        value = int(raw)
    except ValueError:
        value = 0
    if value < 1:
        raise ValueError(f"MIA_VISITOR_DAILY_LIMIT deve ser um inteiro >= 1, veio {raw!r}.")
    return value


async def invocations_always_200(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """AgentCore turns any non-200 from /invocations into an error and drops the body, so the
    container always answers 200; the proxy derives the real status from the body (spec 4.7a)."""
    response = await call_next(request)
    if request.url.path != "/invocations" or response.status_code == 200:
        return response
    body = b"".join([chunk async for chunk in response.body_iterator])  # type: ignore[attr-defined]
    return Response(content=body, status_code=200, media_type=response.headers.get("content-type"))


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
    app = create_app(build_deps(os.environ if env is None else env))
    app.middleware("http")(invocations_always_200)
    return app
