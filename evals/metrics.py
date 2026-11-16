"""Aggregated metrics for eval set A (judge vs. human), task 2.6.

Metric functions are pure: they take lists and return numbers (or None when there is
no data, shown as "n/d" in the report). File reading and the report come later.
"""

import argparse
import json
import math
import sys
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from mia.schemas import RunRecord

SCALE: tuple[int, ...] = (1, 2, 3, 4, 5)


@dataclass(frozen=True)
class JudgedItem:
    """One judge result for one golden item, under one provider label (model)."""

    item_id: str
    label: str
    variant: str
    split: str | None
    paraphrase_of: str | None
    human_score: int | None
    judge_score: int | None  # None = provider error or output outside the schema
    quotes_ok: bool | None


@dataclass(frozen=True)
class Agreement:
    n: int
    weighted_kappa: float | None
    mean_error: float | None
    mean_abs_error: float | None
    pct_within_one: float | None


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _pct(hits: int, total: int) -> float | None:
    return 100 * hits / total if total else None


def weighted_kappa(
    judge: Sequence[int], human: Sequence[int], *, categories: Sequence[int] = SCALE
) -> float | None:
    """Cohen's kappa with quadratic weights. None when undefined (no data or no variation)."""
    if len(judge) != len(human):
        raise ValueError("judge and human must have the same length")
    n = len(judge)
    if n == 0:
        return None
    span = (max(categories) - min(categories)) ** 2

    def weight(a: int, b: int) -> float:
        return (a - b) ** 2 / span

    observed = sum(weight(j, h) for j, h in zip(judge, human, strict=True)) / n
    judge_freq = {c: judge.count(c) / n for c in categories}
    human_freq = {c: human.count(c) / n for c in categories}
    expected = sum(
        judge_freq[a] * human_freq[b] * weight(a, b) for a in categories for b in categories
    )
    if expected == 0:
        return None
    return 1 - observed / expected


def _scored(items: Sequence[JudgedItem]) -> list[JudgedItem]:
    return [i for i in items if i.judge_score is not None and i.human_score is not None]


def agreement(items: Sequence[JudgedItem]) -> Agreement:
    """Judge x human agreement over items that have both scores."""
    scored = _scored(items)
    judge = [i.judge_score for i in scored if i.judge_score is not None]
    human = [i.human_score for i in scored if i.human_score is not None]
    diffs = [j - h for j, h in zip(judge, human, strict=True)]
    return Agreement(
        n=len(scored),
        weighted_kappa=weighted_kappa(judge, human),
        mean_error=_mean(diffs),
        mean_abs_error=_mean([abs(d) for d in diffs]),
        pct_within_one=_pct(sum(abs(d) <= 1 for d in diffs), len(diffs)),
    )


def verbosity_bias(items: Sequence[JudgedItem]) -> tuple[float | None, int]:
    """Mean (judge - human) on "rambling" answers, and how many were used."""
    diffs = [
        i.judge_score - i.human_score
        for i in _scored(items)
        if i.variant == "rambling" and i.judge_score is not None and i.human_score is not None
    ]
    return _mean(diffs), len(diffs)


def paraphrase_consistency(
    items: Sequence[JudgedItem],
) -> tuple[float | None, float | None, int]:
    """Mean |score(paraphrase) - score(original)|, % of equal pairs, number of pairs."""
    scores = {(i.label, i.item_id): i.judge_score for i in items if i.judge_score is not None}
    diffs: list[int] = []
    for item in items:
        if item.paraphrase_of is None or item.judge_score is None:
            continue
        original = scores.get((item.label, item.paraphrase_of))
        if original is not None:
            diffs.append(abs(item.judge_score - original))
    return _mean(diffs), _pct(sum(d == 0 for d in diffs), len(diffs)), len(diffs)


def repeat_consistency(
    items: Sequence[JudgedItem],
) -> tuple[float | None, float | None, int]:
    """Mean (max - min) score per repeated item, % identical across runs, items repeated."""
    runs: dict[tuple[str, str], list[int]] = defaultdict(list)
    for item in items:
        if item.judge_score is not None:
            runs[(item.label, item.item_id)].append(item.judge_score)
    ranges = [max(s) - min(s) for s in runs.values() if len(s) > 1]
    return _mean(ranges), _pct(sum(r == 0 for r in ranges), len(ranges)), len(ranges)


@dataclass(frozen=True)
class RunStats:
    """Call-level numbers for one (model, prompt) pair, taken from RunRecords."""

    model: str
    prompt_name: str
    n: int
    json_valid_pct: float | None
    cost_total: float
    cost_mean: float
    p50_ms: float | None
    p95_ms: float | None


def percentile(values: Sequence[float], p: float) -> float | None:
    """Nearest-rank percentile: the smallest value with at least p% of values <= it."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(p / 100 * len(ordered)))
    return ordered[rank - 1]


def run_stats(records: Sequence[RunRecord]) -> list[RunStats]:
    """One row per (model, prompt_name). JSON validity ignores records where it is None."""
    groups: dict[tuple[str, str], list[RunRecord]] = defaultdict(list)
    for record in records:
        groups[(record.model, record.prompt_name)].append(record)
    stats: list[RunStats] = []
    for (model, prompt_name), group in sorted(groups.items()):
        applicable = [r.json_valid_first_try for r in group if r.json_valid_first_try is not None]
        latencies = [float(r.latency_ms) for r in group]
        total = sum(r.cost_usd for r in group)
        stats.append(
            RunStats(
                model=model,
                prompt_name=prompt_name,
                n=len(group),
                json_valid_pct=_pct(sum(applicable), len(applicable)),
                cost_total=total,
                cost_mean=total / len(group),
                p50_ms=percentile(latencies, 50),
                p95_ms=percentile(latencies, 95),
            )
        )
    return stats


def load_runs(paths: Sequence[Path], experiment: str | None) -> list[RunRecord]:
    """Read RunRecords from JSONL files, keeping only the given experiment (None = all)."""
    records: list[RunRecord] = []
    for path in paths:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                record = RunRecord.model_validate_json(line)
            except ValidationError as exc:
                raise ValueError(f"{path.name} line {number}: not a RunRecord") from exc
            if experiment is None or record.experiment == experiment:
                records.append(record)
    return records


def _judge_score(result: dict[str, Any]) -> tuple[int | None, bool | None]:
    """(score, quotes_ok) from one Promptfoo result; (None, None) on error or bad output."""
    response = result.get("response") or {}
    output = response.get("output") or ""
    try:
        data = json.loads(output)
    except (json.JSONDecodeError, TypeError):
        return None, None
    score = data.get("score") if isinstance(data, dict) else None
    if isinstance(score, bool) or score not in SCALE:
        return None, None
    return score, _quotes_ok(result, data)


def _quotes_ok(result: dict[str, Any], data: dict[str, Any]) -> bool | None:
    grading = result.get("gradingResult") or {}
    for component in grading.get("componentResults") or []:
        value = str((component.get("assertion") or {}).get("value", ""))
        if value.endswith("assert_quotes_verified"):
            return bool(component.get("pass"))
    flag = data.get("quotes_verified")
    return flag if isinstance(flag, bool) else None


def _judged_item(result: dict[str, Any]) -> JudgedItem:
    item = (result.get("testCase") or {}).get("vars", {}).get("item") or {}
    if isinstance(item, str):
        item = json.loads(item)
    score, quotes_ok = _judge_score(result)
    return JudgedItem(
        item_id=item["item_id"],
        label=(result.get("provider") or {}).get("label") or "default",
        variant=item.get("variant", ""),
        split=item.get("split"),
        paraphrase_of=item.get("paraphrase_of"),
        human_score=item.get("human_score"),
        judge_score=score,
        quotes_ok=quotes_ok,
    )


def load_promptfoo_export(path: Path) -> list[JudgedItem]:
    """Read the JSON written by `promptfoo eval --output`; one JudgedItem per result."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        results = raw["results"]["results"]
        return [_judged_item(r) for r in results]
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as exc:
        raise ValueError(f"{path.name}: not a Promptfoo export") from exc


# --- report -----------------------------------------------------------------

ND = "n/d"
SPLITS: tuple[tuple[str, str | None], ...] = (
    ("dev", "dev"),
    ("test (oficial)", "test"),
    ("todos", None),
)


def _fmt(value: float | None, digits: int = 2, suffix: str = "") -> str:
    return ND if value is None else f"{value:.{digits}f}{suffix}"


def _table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return lines


def _by_label(items: Sequence[JudgedItem]) -> dict[str, list[JudgedItem]]:
    groups: dict[str, list[JudgedItem]] = defaultdict(list)
    for item in items:
        groups[item.label].append(item)
    return dict(sorted(groups.items()))


def _agreement_section(groups: dict[str, list[JudgedItem]]) -> list[str]:
    rows: list[list[str]] = []
    for label, items in groups.items():
        for name, split in SPLITS:
            subset = [i for i in items if split is None or i.split == split]
            a = agreement(subset)
            rows.append(
                [
                    label,
                    name,
                    str(a.n),
                    _fmt(a.weighted_kappa),
                    _fmt(a.mean_error),
                    _fmt(a.mean_abs_error),
                    _fmt(a.pct_within_one, 1, "%"),
                ]
            )
    header = ["Modelo", "Split", "n", "Kappa ponderado (quadrático)", "Erro médio", "MAE", "% ±1"]
    return ["## Concordância juiz × humano", "", *_table(header, rows), ""]


def _bias_section(groups: dict[str, list[JudgedItem]]) -> list[str]:
    rows = []
    for label, items in groups.items():
        bias, n = verbosity_bias(items)
        rows.append([label, _fmt(bias), str(n)])
    table = _table(["Modelo", "Viés (juiz − humano, rambling)", "n"], rows)
    return ["## Viés de verbosidade", "", *table, ""]


def _consistency_section(groups: dict[str, list[JudgedItem]]) -> list[str]:
    rows = []
    for label, items in groups.items():
        p_mean, p_same, p_n = paraphrase_consistency(items)
        r_mean, r_same, r_n = repeat_consistency(items)
        rows.append(
            [
                label,
                _fmt(p_mean),
                _fmt(p_same, 1, "%"),
                str(p_n),
                _fmt(r_mean),
                _fmt(r_same, 1, "%"),
                str(r_n),
            ]
        )
    header = [
        "Modelo",
        "Paráfrase: Δ absoluto médio",
        "Paráfrase: % iguais",
        "Pares",
        "Execuções: desvio médio",
        "Execuções: % idênticos",
        "Itens repetidos",
    ]
    return ["## Consistência", "", *_table(header, rows), ""]


def _quotes_section(groups: dict[str, list[JudgedItem]]) -> list[str]:
    rows = []
    for label, items in groups.items():
        valid = [i for i in items if i.judge_score is not None]
        checked = [i for i in valid if i.quotes_ok is not None]
        rows.append(
            [
                label,
                str(len(items)),
                str(len(items) - len(valid)),
                _fmt(_pct(sum(bool(i.quotes_ok) for i in checked), len(checked)), 1, "%"),
            ]
        )
    header = ["Modelo", "Itens", "Excluídos (erro/fora do schema)", "Citações verificáveis"]
    return ["## Citações verificáveis e itens excluídos", "", *_table(header, rows), ""]


def _cost_section(records: Sequence[RunRecord]) -> list[str]:
    if not records:
        return ["## Custo e latência", "", "Sem registros de runs para este experimento.", ""]
    rows = [
        [
            s.model,
            s.prompt_name,
            str(s.n),
            _fmt(s.json_valid_pct, 1, "%"),
            f"{s.cost_total:.4f}",
            f"{s.cost_mean:.5f}",
            _fmt(s.p50_ms, 0),
            _fmt(s.p95_ms, 0),
        ]
        for s in run_stats(records)
    ]
    header = [
        "Modelo",
        "Prompt",
        "Chamadas",
        "JSON válido (1ª tentativa)",
        "Custo total (US$)",
        "Custo médio (US$)",
        "p50 (ms)",
        "p95 (ms)",
    ]
    return ["## Custo e latência", "", *_table(header, rows), ""]


def render_report(
    experiment: str,
    items: Sequence[JudgedItem],
    records: Sequence[RunRecord],
    sources: Sequence[Path],
) -> str:
    """Markdown report: one row per model in each table. "n/d" where there is no data."""
    groups = _by_label(items)
    header = [
        f"# Métricas — {experiment}",
        "",
        f"- Data: {datetime.now(UTC).strftime('%Y-%m-%d')}",
        f"- Fontes: {', '.join(p.name for p in sources) or ND}",
        f"- Itens no export: {len(items)} · registros de runs: {len(records)}",
        "",
    ]
    sections = [
        *_agreement_section(groups),
        *_bias_section(groups),
        *_consistency_section(groups),
        *_quotes_section(groups),
        *_cost_section(records),
    ]
    return "\n".join([*header, *sections])


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Aggregate eval metrics into results/<exp>.md")
    parser.add_argument("--export", type=Path, required=True, help="promptfoo --output JSON")
    parser.add_argument("--runs", type=Path, nargs="+", required=True, help="runs/*.jsonl")
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--out-dir", type=Path, default=Path("results"))
    args = parser.parse_args(argv)
    try:
        items = load_promptfoo_export(args.export)
        records = load_runs(args.runs, args.experiment)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    report = render_report(args.experiment, items, records, [args.export, *args.runs])
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / f"{args.experiment}.md"
    out.write_text(report, encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
