"""Task 1.9: run the real report graph on fictional turns.

Usage:
    uv run python scripts/report_demo.py

Uses the test fixtures (fictional plan and turns) with the scores removed, so the
real judge scores every answered turn. Spends about 6 model calls. Exit codes:
0 report and summary valid, 1 validation rule failed, 2 model call failed.
"""

import json
import sys
from pathlib import Path

from pydantic import ValidationError

from mia.judge import default_scorer
from mia.llm import LLMInvalidOutputError, ModelConfigError
from mia.report_graph import ReportError, ReportResult, run_report
from mia.schemas import InterviewPlan, Turn

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
SESSION_ID = "report-demo"


def load_inputs() -> tuple[InterviewPlan, list[Turn]]:
    plan = InterviewPlan.model_validate_json(
        (FIXTURES / "prep" / "plan_ok.json").read_text(encoding="utf-8")
    )
    raw_turns = json.loads((FIXTURES / "report" / "turns.json").read_text(encoding="utf-8"))
    for raw in raw_turns:
        raw.pop("score", None)  # force the real judge to score every answer
    return plan, [Turn.model_validate(raw) for raw in raw_turns]


def print_result(result: ReportResult) -> None:
    report, summary = result.report, result.summary
    print(f"== Relatório: nota geral {report.overall_score}")
    for comp in report.competencies:
        print(f"- {comp.competency}: {comp.score} — {comp.summary}")
    print(f"pontos fortes: {report.strengths}")
    for imp in report.improvements:
        print(f"melhoria ({imp.question_id}): {imp.issue} → {imp.stronger_answer}")
    print(f"\n== Resumo do recrutador: {summary.headline}")
    print(f"resumo: {summary.summary}")
    for point in summary.strengths:
        print(f'+ {point.point} | "{point.answer_quote}"')
    for point in summary.concerns:
        print(f'- {point.point} | "{point.answer_quote}"')
    print(f"próximo passo ({summary.suggested_next_step}): {summary.next_step_reason}")


def main() -> int:
    plan, turns = load_inputs()
    try:
        result = run_report(
            plan,
            turns,
            scorer=default_scorer(session_id=SESSION_ID),
            session_id=SESSION_ID,
        )
    except ValidationError:
        print("Falha na chamada ao modelo: configuração inválida.", file=sys.stderr)
        return 2
    except (LLMInvalidOutputError, ModelConfigError) as exc:
        print(f"Falha na chamada ao modelo: {exc}", file=sys.stderr)
        return 2
    except ReportError as exc:
        print(f"FALHOU: regra do relatório não passou: {exc}", file=sys.stderr)
        return 1
    print_result(result)
    print("\nOK: relatório e resumo válidos")
    return 0


if __name__ == "__main__":
    # Windows pipes default to cp1252: print accents as UTF-8.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    sys.exit(main())
