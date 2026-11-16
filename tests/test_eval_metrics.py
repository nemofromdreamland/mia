"""Tests for the aggregated set A metrics (task 2.6)."""

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import pytest

from mia.schemas import RunRecord

METRICS_PATH = Path(__file__).resolve().parents[1] / "evals" / "metrics.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("eval_metrics", METRICS_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["eval_metrics"] = module
    spec.loader.exec_module(module)
    return module


m = _load_module()


def _item(
    item_id: str,
    judge: int | None,
    human: int | None,
    *,
    variant: str = "level_3",
    split: str | None = "test",
    paraphrase_of: str | None = None,
    label: str = "model-a",
) -> object:
    return m.JudgedItem(
        item_id=item_id,
        label=label,
        variant=variant,
        split=split,
        paraphrase_of=paraphrase_of,
        human_score=human,
        judge_score=judge,
        quotes_ok=True,
    )


# --- weighted kappa ---------------------------------------------------------


def test_kappa_perfect_agreement() -> None:
    assert m.weighted_kappa([1, 2, 3, 4, 5], [1, 2, 3, 4, 5]) == pytest.approx(1.0)


def test_kappa_hand_computed() -> None:
    # observed weighted disagreement 0.025, expected 0.175 -> 1 - 1/7
    assert m.weighted_kappa([1, 2, 3, 4, 5], [2, 2, 3, 4, 4]) == pytest.approx(6 / 7, abs=1e-6)


def test_kappa_without_variation_is_none() -> None:
    assert m.weighted_kappa([3, 3, 3], [3, 3, 3]) is None


def test_kappa_empty_is_none() -> None:
    assert m.weighted_kappa([], []) is None


def test_kappa_length_mismatch_raises() -> None:
    with pytest.raises(ValueError):
        m.weighted_kappa([1, 2], [1])


# --- agreement --------------------------------------------------------------


def test_agreement_errors_and_within_one() -> None:
    items = [_item("a", 5, 4), _item("b", 3, 3), _item("c", 1, 3)]
    result = m.agreement(items)
    assert result.n == 3
    assert result.mean_error == pytest.approx(-1 / 3)
    assert result.mean_abs_error == pytest.approx(1.0)
    assert result.pct_within_one == pytest.approx(200 / 3)


def test_agreement_skips_missing_scores() -> None:
    items = [_item("a", 4, 4), _item("b", None, 3), _item("c", 2, None)]
    assert m.agreement(items).n == 1


def test_agreement_empty_is_all_none() -> None:
    result = m.agreement([])
    assert result.n == 0
    assert result.weighted_kappa is None
    assert result.mean_error is None
    assert result.mean_abs_error is None
    assert result.pct_within_one is None


# --- verbosity bias ---------------------------------------------------------


def test_verbosity_bias_only_rambling() -> None:
    items = [
        _item("r1", 4, 2, variant="rambling"),
        _item("r2", 3, 2, variant="rambling"),
        _item("l5", 1, 5, variant="level_5"),
    ]
    assert m.verbosity_bias(items) == (pytest.approx(1.5), 2)


def test_verbosity_bias_without_rambling() -> None:
    assert m.verbosity_bias([_item("l5", 5, 5, variant="level_5")]) == (None, 0)


# --- paraphrase consistency -------------------------------------------------


def test_paraphrase_consistency() -> None:
    items = [
        _item("o1", 4, 4),
        _item("p1", 3, 4, variant="paraphrase", paraphrase_of="o1"),
        _item("o2", 5, 5),
        _item("p2", 5, 5, variant="paraphrase", paraphrase_of="o2"),
    ]
    mean_diff, pct_equal, n = m.paraphrase_consistency(items)
    assert mean_diff == pytest.approx(0.5)
    assert pct_equal == pytest.approx(50.0)
    assert n == 2


def test_paraphrase_without_original_score_is_skipped() -> None:
    items = [
        _item("o1", None, 4),
        _item("p1", 3, 4, variant="paraphrase", paraphrase_of="o1"),
    ]
    assert m.paraphrase_consistency(items) == (None, None, 0)


# --- repeat consistency -----------------------------------------------------


def test_repeat_consistency() -> None:
    items = [_item("x", s, 3) for s in (3, 4, 3)] + [_item("y", 5, 5) for _ in range(3)]
    mean_range, pct_identical, n = m.repeat_consistency(items)
    assert mean_range == pytest.approx(0.5)
    assert pct_identical == pytest.approx(50.0)
    assert n == 2


def test_repeat_consistency_single_run_is_none() -> None:
    items = [_item("x", 3, 3), _item("y", 4, 4)]
    assert m.repeat_consistency(items) == (None, None, 0)


def test_repeat_consistency_does_not_mix_labels() -> None:
    items = [_item("x", 3, 3, label="a"), _item("x", 5, 3, label="b")]
    assert m.repeat_consistency(items) == (None, None, 0)


# --- percentile and run stats ----------------------------------------------


def test_percentile_nearest_rank() -> None:
    assert m.percentile([float(v) for v in range(100, 2100, 100)], 95) == 1900


def test_percentile_empty_is_none() -> None:
    assert m.percentile([], 95) is None


def _record(
    *, valid: bool | None, cost: float, latency: int, model: str = "haiku", prompt: str = "judge"
) -> RunRecord:
    return RunRecord(
        run_id="r",
        experiment="exp",
        session_id=None,
        prompt_name=prompt,
        prompt_version=1,
        provider="bedrock",
        model=model,
        params={},
        input_hash="h",
        input={},
        output_raw="",
        output_parsed=None,
        json_valid_first_try=valid,
        repaired=None,
        input_tokens=1,
        output_tokens=1,
        latency_ms=latency,
        cost_usd=cost,
        error=None,
        created_at=datetime(2026, 11, 16, tzinfo=UTC),
    )


def test_run_stats_groups_and_ignores_none_for_json_validity() -> None:
    records = [
        _record(valid=None, cost=0.01, latency=100),
        _record(valid=False, cost=0.02, latency=200),
        _record(valid=True, cost=0.03, latency=300),
        _record(valid=True, cost=1.0, latency=50, model="other"),
    ]
    stats = {s.model: s for s in m.run_stats(records)}
    assert len(stats) == 2
    haiku = stats["haiku"]
    assert haiku.n == 3
    assert haiku.json_valid_pct == pytest.approx(50.0)
    assert haiku.cost_total == pytest.approx(0.06)
    assert haiku.cost_mean == pytest.approx(0.02)
    assert haiku.p50_ms == 200
    assert haiku.p95_ms == 300


def test_run_stats_json_validity_not_applicable_is_none() -> None:
    (stat,) = m.run_stats([_record(valid=None, cost=0.0, latency=10)])
    assert stat.json_valid_pct is None


def test_load_runs_filters_by_experiment(tmp_path: Path) -> None:
    keep = _record(valid=True, cost=0.01, latency=10)
    other = keep.model_copy(update={"experiment": "other"})
    path = tmp_path / "runs.jsonl"
    path.write_text(
        keep.model_dump_json() + "\n\n" + other.model_dump_json() + "\n", encoding="utf-8"
    )
    assert len(m.load_runs([path], "exp")) == 1
    assert len(m.load_runs([path], None)) == 2


def test_load_runs_rejects_bad_format(tmp_path: Path) -> None:
    path = tmp_path / "runs.jsonl"
    path.write_text("not json\n", encoding="utf-8")
    with pytest.raises(ValueError, match="runs.jsonl"):
        m.load_runs([path], None)


# --- promptfoo export -------------------------------------------------------

FIXTURE = Path(__file__).parent / "fixtures" / "promptfoo_export_small.json"


def test_load_export_reads_scores_labels_and_quotes() -> None:
    items = m.load_promptfoo_export(FIXTURE)
    assert len(items) == 6
    assert {i.label for i in items} == {"model-a", "model-b"}
    first = next(i for i in items if i.label == "model-a" and i.item_id == "q1-level_5")
    assert (first.judge_score, first.human_score, first.split) == (5, 5, "dev")
    assert first.quotes_ok is True
    bad_quotes = next(i for i in items if i.item_id == "q1-level_3" and i.label == "model-a")
    assert bad_quotes.judge_score == 4
    assert bad_quotes.quotes_ok is False


def test_load_export_provider_error_has_no_score() -> None:
    items = m.load_promptfoo_export(FIXTURE)
    failed = next(i for i in items if i.label == "model-b" and i.item_id == "q1-level_3")
    assert failed.judge_score is None
    assert failed.quotes_ok is None


def test_provider_error_ignores_residual_valid_output() -> None:
    result = {
        "response": {
            "error": "provider failed after producing output",
            "output": '{"score": 5, "quotes_verified": true}',
        }
    }

    assert m._judge_score(result) == (None, None)


def test_load_export_keeps_paraphrase_link() -> None:
    items = m.load_promptfoo_export(FIXTURE)
    para = next(i for i in items if i.variant == "paraphrase")
    assert para.paraphrase_of == "q1-level_5"


def test_agreement_per_label_from_export() -> None:
    items = m.load_promptfoo_export(FIXTURE)
    by_label = {
        label: m.agreement([i for i in items if i.label == label])
        for label in ("model-a", "model-b")
    }
    assert by_label["model-a"].n == 4  # 4 scored items
    assert by_label["model-b"].n == 1  # the error one is excluded


def test_load_export_rejects_wrong_format(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text('{"foo": 1}', encoding="utf-8")
    with pytest.raises(ValueError, match="bad.json"):
        m.load_promptfoo_export(path)


# --- report and CLI ---------------------------------------------------------


def _report(items: list[object] | None = None, records: list[RunRecord] | None = None) -> str:
    loaded = m.load_promptfoo_export(FIXTURE) if items is None else items
    return m.render_report("exp", loaded, records or [], [FIXTURE])


def test_render_report_has_all_sections_and_header() -> None:
    text = _report(records=[_record(valid=True, cost=0.01, latency=100)])
    for heading in (
        "Concordância",
        "Viés de verbosidade",
        "Consistência",
        "Citações verificáveis",
        "Custo e latência",
    ):
        assert heading in text
    assert "promptfoo_export_small.json" in text  # source file in the header
    assert "Kappa ponderado (quadrático)" in text


def test_render_report_splits_and_marks_test_as_official() -> None:
    text = _report()
    assert "| model-a | dev |" in text
    assert "| model-a | test (oficial) |" in text
    assert "| model-a | todos |" in text


def test_render_report_one_row_per_label() -> None:
    text = _report()
    assert "| model-a | todos |" in text
    assert "| model-b | todos |" in text


def test_render_report_shows_nd_and_excluded_count() -> None:
    text = _report()
    assert "n/d" in text  # no repeated runs -> repeat consistency is n/d
    # model-b has 1 provider error in the fixture
    section = text.split("## Citações")[1].split("## Custo")[0]
    row = next(r for r in section.splitlines() if r.startswith("| model-b |"))
    cells = [c.strip() for c in row.strip("|").split("|")]
    assert cells[2] == "1"  # Modelo | Itens | Excluídos | Citações verificáveis


def test_render_report_without_runs_says_so() -> None:
    assert "Sem registros" in _report(records=[])


def test_render_report_handles_empty_items() -> None:
    text = m.render_report("exp", [], [], [])
    assert "Concordância" in text


def _write_inputs(tmp_path: Path) -> Path:
    runs = tmp_path / "runs.jsonl"
    runs.write_text(
        _record(valid=True, cost=0.01, latency=100).model_dump_json() + "\n", encoding="utf-8"
    )
    return runs


def test_cli_happy_path_writes_markdown(tmp_path: Path) -> None:
    runs = _write_inputs(tmp_path)
    code = m.main(
        [
            "--export", str(FIXTURE),
            "--runs", str(runs),
            "--experiment", "exp",
            "--out-dir", str(tmp_path),
        ]
    )  # fmt: skip
    assert code == 0
    assert "Concordância" in (tmp_path / "exp.md").read_text(encoding="utf-8")


def test_cli_missing_export_fails_without_writing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = m.main(
        [
            "--export", str(tmp_path / "nao_existe.json"),
            "--runs", str(_write_inputs(tmp_path)),
            "--experiment", "exp",
            "--out-dir", str(tmp_path),
        ]
    )  # fmt: skip
    assert code == 1
    assert "nao_existe.json" in capsys.readouterr().err
    assert not (tmp_path / "exp.md").exists()


def test_cli_wrong_format_fails_without_writing(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text('{"foo": 1}', encoding="utf-8")
    code = m.main(
        [
            "--export", str(bad),
            "--runs", str(_write_inputs(tmp_path)),
            "--experiment", "exp",
            "--out-dir", str(tmp_path),
        ]
    )  # fmt: skip
    assert code == 1
    assert not (tmp_path / "exp.md").exists()


def test_render_report_tables_are_well_formed() -> None:
    text = _report(records=[_record(valid=True, cost=0.01, latency=100)])
    table: list[str] = []
    for line in [*text.splitlines(), ""]:
        if line.startswith("|"):
            table.append(line)
            continue
        assert len({row.count("|") for row in table}) <= 1  # same column count in every row
        table = []


# --- set B (tool decisions), task 2.7 ----------------------------------------

FIXTURE_B = Path(__file__).parent / "fixtures" / "promptfoo_export_set_b_small.json"


def _tool(
    expected: str, got: str | None, args_ok: bool | None = None, label: str = "model-a"
) -> object:
    return m.ToolItem(
        item_id="b", label=label, split="test",
        expected_action=expected, got_action=got, args_ok=args_ok,
    )  # fmt: skip


def test_tool_accuracy_counts_errors_and_confusion() -> None:
    items = [
        _tool("end", "end"),
        _tool("next_question", "next_question"),
        _tool("follow_up", "follow_up", True),
        _tool("end", None),
    ]
    result = m.tool_accuracy(items)
    assert result.n == 4
    assert result.action_pct == 75.0
    assert result.errors == 1
    assert result.confusion[("end", "erro")] == 1
    assert result.confusion[("end", "end")] == 1


def test_tool_accuracy_args_only_over_follow_up_items() -> None:
    items = [_tool("follow_up", "follow_up", True), _tool("follow_up", "follow_up", False)]
    items.append(_tool("end", "end"))
    result = m.tool_accuracy(items)
    assert result.args_pct == 50.0
    assert result.args_n == 2


def test_tool_accuracy_wrong_action_counts_as_args_miss() -> None:
    # expected follow_up but the action was wrong: the argument cannot be right
    result = m.tool_accuracy([_tool("follow_up", "next_question", None)])
    assert result.args_pct == 0.0
    assert result.args_n == 1


def test_tool_accuracy_empty_is_none() -> None:
    result = m.tool_accuracy([])
    assert result.n == 0 and result.action_pct is None and result.args_pct is None


def test_load_tool_export_reads_labels_splits_and_actions() -> None:
    items = m.load_tool_export(FIXTURE_B)
    assert len(items) == 6
    first = items[0]
    assert (first.label, first.split, first.expected_action) == ("model-a", "dev", "follow_up")
    assert first.got_action == "follow_up" and first.args_ok is True
    assert items[2].got_action == "next_question" and items[2].expected_action == "end"
    assert items[3].args_ok is False


def test_load_tool_export_uses_effective_action() -> None:
    # model-b b2: raw follow_up but no follow-ups left -> next_question
    assert m.load_tool_export(FIXTURE_B)[4].got_action == "next_question"


def test_load_tool_export_provider_error_has_no_action() -> None:
    assert m.load_tool_export(FIXTURE_B)[5].got_action is None


def test_load_tool_export_rejects_wrong_format(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError):
        m.load_tool_export(bad)


def test_load_runs_experiment_prefix(tmp_path: Path) -> None:
    a = _record(valid=True, cost=0.01, latency=10).model_copy(
        update={"experiment": "baseline_v1_set_a"}
    )
    other = a.model_copy(update={"experiment": "baseline_v10"})
    path = tmp_path / "runs.jsonl"
    path.write_text(a.model_dump_json() + "\n" + other.model_dump_json() + "\n", encoding="utf-8")
    assert len(m.load_runs([path], "baseline_v1")) == 1


def test_render_report_has_set_b_section() -> None:
    text = m.render_report(
        "exp", m.load_promptfoo_export(FIXTURE), [], [FIXTURE],
        tool_items=m.load_tool_export(FIXTURE_B),
    )  # fmt: skip
    assert "Conjunto B" in text
    section = text.split("Conjunto B")[1]
    assert "| model-b | test (oficial) |" in section
    assert "Matriz de confusão" in section
    assert "erro" in section


def test_render_report_without_tool_items_has_no_set_b() -> None:
    assert "Conjunto B" not in _report()


def test_cli_with_export_b_writes_set_b(tmp_path: Path) -> None:
    code = m.main(
        [
            "--export", str(FIXTURE),
            "--export-b", str(FIXTURE_B),
            "--runs", str(_write_inputs(tmp_path)),
            "--experiment", "exp",
            "--out-dir", str(tmp_path),
        ]
    )  # fmt: skip
    assert code == 0
    assert "Conjunto B" in (tmp_path / "exp.md").read_text(encoding="utf-8")


def test_cli_missing_export_b_fails_without_writing(tmp_path: Path) -> None:
    code = m.main(
        [
            "--export", str(FIXTURE),
            "--export-b", str(tmp_path / "nao_existe_b.json"),
            "--runs", str(_write_inputs(tmp_path)),
            "--experiment", "exp",
            "--out-dir", str(tmp_path),
        ]
    )  # fmt: skip
    assert code == 1
    assert not (tmp_path / "exp.md").exists()


def test_render_report_with_set_b_tables_are_well_formed() -> None:
    text = m.render_report("exp", [], [], [], tool_items=m.load_tool_export(FIXTURE_B))
    table: list[str] = []
    for line in [*text.splitlines(), ""]:
        if line.startswith("|"):
            table.append(line)
            continue
        assert len({row.count("|") for row in table}) <= 1
        table = []
