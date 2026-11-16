"""Tests for the `mia simulate` CLI (no real model: every dependency is a fake)."""

import io
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from mia.cli import build_parser, main, run_simulate
from mia.prep_graph import PrepResult, PrepValidationError
from mia.report_graph import ReportResult
from mia.repositories import InMemorySessionRepository
from mia.schemas import (
    AnswerScore,
    CandidateSummary,
    InterviewPlan,
    Report,
    Screening,
    ToolDecision,
    Turn,
)
from mia.simulation import SimulationDeps

PREP = Path(__file__).parent / "fixtures" / "prep"
REPORT = Path(__file__).parent / "fixtures" / "report"
T0 = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)


def clock() -> datetime:
    return T0


def fixture_prep(data) -> PrepResult:
    return PrepResult(
        screening=Screening.model_validate_json((PREP / "screening_ok.json").read_text("utf-8")),
        plan=InterviewPlan.model_validate_json((PREP / "plan_ok.json").read_text("utf-8")),
    )


def fixture_report(plan, turns: list[Turn]) -> ReportResult:
    score = AnswerScore(
        score=4, criteria_met=[], evidence_quotes=[], justification="ok", quotes_verified=True
    )
    return ReportResult(
        report=Report.model_validate_json((REPORT / "report_ok.json").read_text("utf-8")),
        summary=CandidateSummary.model_validate_json(
            (REPORT / "summary_ok.json").read_text("utf-8")
        ),
        turns=[t.model_copy(update={"score": score}) if t.answer_text else t for t in turns],
    )


def fake_scorer(question, answer) -> AnswerScore:
    return AnswerScore(
        score=3, criteria_met=[], evidence_quotes=[], justification="ok", quotes_verified=True
    )


def make_deps(prep=fixture_prep) -> SimulationDeps:
    return SimulationDeps(
        repo=InMemorySessionRepository(clock=clock),
        decider=lambda q, a, s, t: ToolDecision(action="next_question", reason="ok"),
        writer=lambda phase, question, instruction, history: f"[{phase}] {question}",
        scorer=fake_scorer,
        clock=clock,
        prep=prep,
        report=fixture_report,
    )


@pytest.fixture
def job_file(tmp_path: Path) -> Path:
    path = tmp_path / "vaga.md"
    path.write_text("Vaga fictícia de analista de dados.", encoding="utf-8")
    return path


def run(job: Path, stdin_text: str, deps: SimulationDeps | None = None):
    args = build_parser().parse_args(
        ["simulate", "--cv", str(PREP / "cv_ficticio.md"), "--job", str(job), "--persona", "hr"]
    )
    out, err = io.StringIO(), io.StringIO()
    code = run_simulate(args, deps or make_deps(), io.StringIO(stdin_text), out, err)
    return code, out.getvalue(), err.getvalue()


def test_no_args_exits_with_2() -> None:
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


def test_missing_option_exits_with_2() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["simulate", "--cv", "a.md", "--job", "b.md"])
    assert exc.value.code == 2


def test_invalid_persona_exits_with_2() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["simulate", "--cv", "a.md", "--job", "b.md", "--persona", "chefe"])
    assert exc.value.code == 2


def test_minutes_out_of_range_exits_with_2() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["simulate", "--cv", "a.md", "--job", "b.md", "--persona", "hr", "--minutes", "99"])
    assert exc.value.code == 2


def test_missing_job_exits_with_1_without_calling_models(tmp_path: Path, capsys) -> None:
    missing = tmp_path / "nao_existe.md"

    code = main(
        ["simulate", "--cv", str(PREP / "cv_ficticio.md"), "--job", str(missing), "--persona", "hr"]
    )

    assert code == 1
    assert str(missing) in capsys.readouterr().err


def test_run_simulate_missing_job_does_not_call_prep(tmp_path: Path) -> None:
    deps = make_deps(prep=lambda data: pytest.fail("prep must not run"))

    code, out, err = run(tmp_path / "nao_existe.md", "", deps)

    assert code == 1
    assert out == ""
    assert "nao_existe.md" in err


def test_full_flow_prints_one_json_on_stdout(job_file: Path) -> None:
    code, out, err = run(job_file, "resp1\nresp2\n/fim\n")

    assert code == 0
    data = json.loads(out)
    assert set(data) == {"session_id", "report", "summary"}
    Report.model_validate(data["report"])
    CandidateSummary.model_validate(data["summary"])
    assert "[opening]" in err
    assert "[opening]" not in out


def test_eof_ends_the_interview_as_visitor(job_file: Path) -> None:
    code, out, err = run(job_file, "")

    assert code == 0
    assert json.loads(out)["session_id"]
    assert "[closing]" in err


def test_plan_done_ends_by_itself(job_file: Path) -> None:
    code, out, _ = run(job_file, "resposta\n" * 50)

    assert code == 0
    assert "report" in json.loads(out)


def test_empty_answer_asks_again(job_file: Path) -> None:
    deps = make_deps()

    code, out, err = run(job_file, "\n/fim\n", deps)

    assert code == 0
    assert "vazia" in err.lower() or "empty" in err.lower()
    assert json.loads(out)["session_id"]


def test_prep_failure_exits_with_1(job_file: Path) -> None:
    def failing(data):
        raise PrepValidationError(["x"])

    code, out, err = run(job_file, "", make_deps(prep=failing))

    assert code == 1
    assert out == ""
    assert err.strip()
