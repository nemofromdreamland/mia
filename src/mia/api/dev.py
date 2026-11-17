"""Local dev server for the frontend: `uv run uvicorn mia.api.dev:app --port 8000`.

In-memory repositories and quotas (state is lost on restart), real model wiring
(same as the CLI). Never used in AWS.
"""

from datetime import UTC, datetime

from fastapi import FastAPI

from mia.api.app import create_app
from mia.cases import CASES_DIR
from mia.interviewer import default_writer, should_follow_up
from mia.judge import default_scorer
from mia.quotas import InMemoryMetaStore, QuotaGate
from mia.report_graph import run_report
from mia.repositories import (
    InMemoryCandidateCounter,
    InMemoryReportStore,
    InMemorySessionRepository,
)
from mia.service import ServiceDeps


def _utc_now() -> datetime:
    return datetime.now(UTC)


def build_dev_deps() -> ServiceDeps:
    scorer = default_scorer()
    return ServiceDeps(
        repo=InMemorySessionRepository(clock=_utc_now),
        reports=InMemoryReportStore(),
        counter=InMemoryCandidateCounter(),
        gate=QuotaGate(InMemoryMetaStore(), clock=_utc_now),
        decider=should_follow_up,
        writer_for=lambda persona: default_writer(persona=persona),
        scorer=scorer,
        report=lambda plan, turns: run_report(plan, turns, scorer=scorer),
        clock=_utc_now,
        cases_dir=CASES_DIR,
    )


def build_app() -> FastAPI:
    return create_app(build_dev_deps())


app = build_app()
