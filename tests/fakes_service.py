"""Shared fakes for the service and API tests (no model, in-memory repositories)."""

from datetime import UTC, datetime, timedelta

import pytest

from mia.cases import CASES_DIR
from mia.report_graph import ReportResult
from mia.repositories import (
    InMemoryCandidateCounter,
    InMemoryReportStore,
    InMemorySessionRepository,
)
from mia.schemas import (
    CandidateSummary,
    CompetencyScore,
    Report,
    SummaryPoint,
    ToolDecision,
)
from mia.service import ServiceDeps, ServiceError, create_session

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


def fake_report_result(plan, turns) -> ReportResult:
    report = Report(
        overall_score=4.0,
        competencies=[CompetencyScore(competency="comunicação", score=4.0, summary="ok")],
        strengths=["claro"],
        improvements=[],
    )
    point = SummaryPoint(point="ok", answer_quote="resposta")
    summary = CandidateSummary(
        headline="Boa entrevista",
        summary="Resumo.",
        strengths=[point],
        concerns=[point],
        suggested_next_step="advance",
        next_step_reason="ok",
    )
    return ReportResult(report=report, summary=summary, turns=turns)


def complete_with_score(
    deps: ServiceDeps, visitor: str, score: float, case_id: str = CASE_ID
) -> str:
    """Create a session and mark it completed with a stored report (no model call)."""
    session = create_session(deps, visitor, case_id, "text")
    result = fake_report_result(None, [])
    report = result.report.model_copy(update={"overall_score": score})
    deps.reports.save(session.session_id, report, result.summary)
    deps.repo.update_session(
        visitor,
        session.session_id,
        expected_status="ready",
        changes={
            "status": "completed",
            "overall_score": score,
            "headline": f"nota {score}",
            "ended_at": T0 + timedelta(minutes=int(score * 10)),
        },
    )
    return session.session_id
