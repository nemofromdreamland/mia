"""Regression tests for the real-model report demo."""

import importlib.util
from pathlib import Path
from types import ModuleType

from mia.report_graph import ReportError


def _load_demo() -> ModuleType:
    path = Path(__file__).parents[1] / "scripts" / "report_demo.py"
    spec = importlib.util.spec_from_file_location("report_demo", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


report_demo = _load_demo()


def test_main_reports_original_scorer_failure(monkeypatch, capsys) -> None:
    scorer_calls = 0

    def failing_scorer(question, answer):
        nonlocal scorer_calls
        scorer_calls += 1
        raise RuntimeError("provider unavailable")

    # Reproduce P1: the graph swallows the scorer error and later reports no scores.
    def graph_with_p1(plan, turns, **options):
        for _ in range(2):
            try:
                options["scorer"](None, "answer")
            except RuntimeError:
                pass
        raise ReportError("no scored turns to build a report from")

    monkeypatch.setattr(report_demo, "default_scorer", lambda **options: failing_scorer)
    monkeypatch.setattr(report_demo, "run_report", graph_with_p1)

    result = report_demo.main()

    captured = capsys.readouterr()
    assert result == 2
    assert "Falha na chamada ao modelo: provider unavailable" in captured.err
    assert "no scored turns" not in captured.err
    assert "Traceback" not in captured.err
    assert scorer_calls == 1


def test_main_keeps_report_error_without_scorer_failure(monkeypatch, capsys) -> None:
    monkeypatch.setattr(report_demo, "default_scorer", lambda **options: lambda q, a: None)
    monkeypatch.setattr(
        report_demo,
        "run_report",
        lambda *args, **kwargs: (_ for _ in ()).throw(ReportError("invalid report")),
    )

    result = report_demo.main()

    captured = capsys.readouterr()
    assert result == 1
    assert "FALHOU: regra do relatório não passou: invalid report" in captured.err
