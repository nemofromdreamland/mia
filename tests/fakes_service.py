"""Shared fakes for the service and API tests (no model, in-memory repositories)."""

from datetime import UTC, datetime, timedelta

import pytest

from mia.cases import CASES_DIR
from mia.repositories import (
    InMemoryCandidateCounter,
    InMemoryReportStore,
    InMemorySessionRepository,
)
from mia.schemas import ToolDecision
from mia.service import ServiceDeps, ServiceError

T0 = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
VISITOR_A = "11111111-1111-4111-8111-111111111111"
VISITOR_B = "22222222-2222-4222-8222-222222222222"
CASE_ID = "software-intern"


class Calls:
    def __init__(self) -> None:
        self.writer = 0
        self.report = 0
        self.gate = 0


class Gate:
    def __init__(self, calls: Calls, error: ServiceError | None = None) -> None:
        self.calls = calls
        self.error = error

    def check(self, visitor_id: str) -> None:
        self.calls.gate += 1
        if self.error:
            raise self.error


def make_deps(
    gate_error: ServiceError | None = None, calls: Calls | None = None, scorer=None
) -> ServiceDeps:
    calls = calls or Calls()
    tick = {"now": T0}

    def clock() -> datetime:
        tick["now"] += timedelta(seconds=1)
        return tick["now"]

    def writer_for(persona):
        def writer(phase, question, instruction, history) -> str:
            calls.writer += 1
            return question

        return writer

    def report(plan, turns):
        calls.report += 1
        raise AssertionError("report not expected")

    return ServiceDeps(
        repo=InMemorySessionRepository(clock=clock),
        reports=InMemoryReportStore(),
        counter=InMemoryCandidateCounter(),
        gate=Gate(calls, gate_error),
        decider=lambda q, a, s, t: ToolDecision(action="next_question", reason="ok"),
        writer_for=writer_for,
        scorer=scorer or (lambda q, a: pytest.fail("scorer not expected")),
        report=report,
        clock=clock,
        cases_dir=CASES_DIR,
    )
