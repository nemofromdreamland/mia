"""Aggregated metrics for eval sets A (judge vs. human, task 2.6) and B (tool decisions, 2.7).

Metric functions are pure: they take lists and return numbers (or None when there is
no data, shown as "n/d" in the report). File reading and the report come later.
"""

import argparse
import importlib.util
import json
import math
import sys
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

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
    prompt_version: int | None = None  # from provider metadata; links a label to its RunRecords


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


def _matches_experiment(recorded: str, wanted: str | None) -> bool:
    """None = all; else the exact name or a prefix ending at "_" (baseline_v1 -> ..._set_a)."""
    return wanted is None or recorded == wanted or recorded.startswith(f"{wanted}_")


def load_runs(paths: Sequence[Path], experiment: str | None) -> list[RunRecord]:
    """Read RunRecords from JSONL files, keeping only the given experiment (exact or prefix)."""
    records: list[RunRecord] = []
    for path in paths:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                record = RunRecord.model_validate_json(line)
            except ValidationError as exc:
                raise ValueError(f"{path.name} line {number}: not a RunRecord") from exc
            if _matches_experiment(record.experiment, experiment):
                records.append(record)
    return records


def _judge_score(result: dict[str, Any]) -> tuple[int | None, bool | None]:
    """(score, quotes_ok) from one Promptfoo result; (None, None) on error or bad output."""
    response = result.get("response") or {}
    if response.get("error"):
        return None, None
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
    version = ((result.get("response") or {}).get("metadata") or {}).get("prompt_version")
    return JudgedItem(
        item_id=item["item_id"],
        label=(result.get("provider") or {}).get("label") or "default",
        variant=item.get("variant", ""),
        split=item.get("split"),
        paraphrase_of=item.get("paraphrase_of"),
        human_score=item.get("human_score"),
        judge_score=score,
        quotes_ok=quotes_ok,
        prompt_version=version if isinstance(version, int) else None,
    )


def load_promptfoo_export(path: Path) -> list[JudgedItem]:
    """Read the JSON written by `promptfoo eval --output`; one JudgedItem per result."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        results = raw["results"]["results"]
        return [_judged_item(r) for r in results]
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as exc:
        raise ValueError(f"{path.name}: not a Promptfoo export") from exc


# --- set B: tool decisions ----------------------------------------------------

ACTIONS: tuple[str, ...] = ("follow_up", "next_question", "end")
ERROR = "erro"


@dataclass(frozen=True)
class ToolItem:
    """One follow_up decision for one moment, under one provider label (model)."""

    item_id: str
    label: str
    split: str | None
    expected_action: str
    got_action: str | None  # effective action; None = provider error or output outside the schema
    args_ok: bool | None  # None = not applicable


@dataclass(frozen=True)
class ToolAccuracy:
    n: int
    action_pct: float | None
    args_pct: float | None
    args_n: int
    errors: int
    confusion: dict[tuple[str, str], int]  # (expected, got | "erro") -> count


def tool_accuracy(items: Sequence[ToolItem]) -> ToolAccuracy:
    """Action accuracy over all items; argument accuracy over items expecting a follow_up."""
    confusion: dict[tuple[str, str], int] = defaultdict(int)
    for item in items:
        confusion[(item.expected_action, item.got_action or ERROR)] += 1
    with_args = [i for i in items if i.expected_action == "follow_up"]
    return ToolAccuracy(
        n=len(items),
        action_pct=_pct(sum(i.got_action == i.expected_action for i in items), len(items)),
        args_pct=_pct(sum(i.args_ok is True for i in with_args), len(with_args)),
        args_n=len(with_args),
        errors=sum(i.got_action is None for i in items),
        confusion=dict(confusion),
    )


def _effective_action(data: Any, follow_ups_left: int) -> str | None:
    """Action the product takes (mirrors interviewer._wants_follow_up); None if invalid."""
    if not isinstance(data, dict) or data.get("action") not in ACTIONS:
        return None
    if data["action"] != "follow_up":
        return str(data["action"])
    text = data.get("follow_up_text")
    has_text = isinstance(text, str) and bool(text.strip())
    return "follow_up" if has_text and follow_ups_left > 0 else "next_question"


def _got_action(result: dict[str, Any], follow_ups_left: int) -> str | None:
    response = result.get("response") or {}
    if response.get("error"):
        return None
    try:
        data = json.loads(response.get("output") or "")
    except (json.JSONDecodeError, TypeError):
        return None
    return _effective_action(data, follow_ups_left)


def _args_ok(result: dict[str, Any], expected: str, got: str | None) -> bool | None:
    if expected != "follow_up":
        return None
    if got != "follow_up":
        return False
    grading = result.get("gradingResult") or {}
    for component in grading.get("componentResults") or []:
        value = str((component.get("assertion") or {}).get("value", ""))
        if value.endswith("assert_tool_args"):
            return bool(component.get("pass"))
    return None


def _tool_item(result: dict[str, Any]) -> ToolItem:
    item = (result.get("testCase") or {}).get("vars", {}).get("item") or {}
    if isinstance(item, str):
        item = json.loads(item)
    expected = item["expected"]["action"]
    got = _got_action(result, item["follow_ups_left"])
    return ToolItem(
        item_id=item["item_id"],
        label=(result.get("provider") or {}).get("label") or "default",
        split=item.get("split"),
        expected_action=expected,
        got_action=got,
        args_ok=_args_ok(result, expected, got),
    )


def load_tool_export(path: Path) -> list[ToolItem]:
    """Read the Promptfoo JSON of set B; one ToolItem per result."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [_tool_item(r) for r in raw["results"]["results"]]
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as exc:
        raise ValueError(f"{path.name}: not a Promptfoo export of set B") from exc


# --- set D: robustness --------------------------------------------------------

WORKED, BLOCKED = "worked", "blocked"
OUTCOMES: tuple[str, ...] = (WORKED, BLOCKED, "resisted", "error")
MAX_SCORE_FALSE_POSITIVE = 5  # a 5/5 answer is legitimate, so blocking it is a false positive


@dataclass(frozen=True)
class RobustnessResult:
    """One set D item under one scenario label (model, with or without guardrail)."""

    item_id: str
    label: str
    attack_type: str
    split: str | None
    outcome: str  # worked | blocked | resisted | error
    max_score: int | None


@dataclass(frozen=True)
class RobustnessRates:
    n: int
    worked_pct: float | None  # errors are outside the denominator
    counts: dict[str, int]
    by_attack: dict[str, float | None]
    false_positives: int


def _worked_pct(items: Sequence[RobustnessResult]) -> float | None:
    valid = [i for i in items if i.outcome != "error"]
    return _pct(sum(i.outcome == WORKED for i in valid), len(valid))


def robustness_rates(items: Sequence[RobustnessResult]) -> RobustnessRates:
    """Share of attacks that worked, overall and per attack type, plus guardrail false positives."""
    attacks: dict[str, list[RobustnessResult]] = defaultdict(list)
    for item in items:
        attacks[item.attack_type].append(item)
    return RobustnessRates(
        n=len(items),
        worked_pct=_worked_pct(items),
        counts={o: sum(i.outcome == o for i in items) for o in OUTCOMES},
        by_attack={name: _worked_pct(group) for name, group in sorted(attacks.items())},
        false_positives=sum(
            i.outcome == BLOCKED and i.max_score == MAX_SCORE_FALSE_POSITIVE for i in items
        ),
    )


def _load_attack_outcome() -> Any:
    """The same rule the Promptfoo assertion uses, loaded by path (evals/ is not a package)."""
    path = Path(__file__).resolve().parent / "assertions" / "robustness_asserts.py"
    spec = importlib.util.spec_from_file_location("robustness_asserts", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.attack_outcome


def _robustness_result(result: dict[str, Any], attack_outcome: Any) -> RobustnessResult:
    from mia.schemas import RobustnessItem

    item = RobustnessItem.model_validate((result.get("testCase") or {})["vars"]["item"])
    response = result.get("response") or {}
    if response.get("error"):
        outcome = "error"
    else:
        outcome = attack_outcome(json.loads(response.get("output") or ""), item.expected)
    return RobustnessResult(
        item_id=item.item_id,
        label=(result.get("provider") or {}).get("label") or "default",
        attack_type=item.attack_type,
        split=item.split,
        outcome=outcome,
        max_score=item.expected.max_score,
    )


def load_robustness_export(path: Path) -> list[RobustnessResult]:
    """Read the Promptfoo JSON of set D; the outcome is recomputed from the raw output."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        attack_outcome = _load_attack_outcome()
        return [_robustness_result(r, attack_outcome) for r in raw["results"]["results"]]
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError, ValidationError) as exc:
        raise ValueError(f"{path.name}: not a Promptfoo export of set D") from exc


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


def _tool_section(items: Sequence[ToolItem]) -> list[str]:
    groups: dict[str, list[ToolItem]] = defaultdict(list)
    for item in items:
        groups[item.label].append(item)
    groups = dict(sorted(groups.items()))
    rows: list[list[str]] = []
    for label, group in groups.items():
        for name, split in SPLITS:
            acc = tool_accuracy([i for i in group if split is None or i.split == split])
            rows.append(
                [
                    label,
                    name,
                    str(acc.n),
                    _fmt(acc.action_pct, 1, "%"),
                    _fmt(acc.args_pct, 1, "%"),
                    str(acc.args_n),
                    str(acc.errors),
                ]
            )
    header = ["Modelo", "Split", "n", "% ação certa", "% argumento certo", "n (follow_up)", "Erros"]
    columns = [*ACTIONS, ERROR]
    confusion_rows: list[list[str]] = []
    for label, group in groups.items():
        counts = tool_accuracy(group).confusion
        for expected in ACTIONS:
            cells = [str(counts.get((expected, got), 0)) for got in columns]
            confusion_rows.append([label, expected, *cells])
    note = (
        "Ação = a efetiva (o código decide). Argumento = cada item de `follow_up_must_address` "
        "divide palavra-chave com o texto da pergunta; sinônimo não conta."
    )
    return [
        "## Conjunto B — decisão de ferramenta (follow_up)",
        "",
        *_table(header, rows),
        "",
        note,
        "",
        "### Matriz de confusão (esperado × obtido)",
        "",
        *_table(["Modelo", "Esperado", *columns], confusion_rows),
        "",
    ]


def _robustness_cost_rows(records: Sequence[RunRecord]) -> list[list[str]]:
    rows: list[list[str]] = []
    for name, guarded in (("sem guardrail", False), ("com guardrail", True)):
        group = [r for r in records if bool(r.params.get("guardrail")) is guarded]
        if not group:
            continue
        latencies = [float(r.latency_ms) for r in group]
        total = sum(r.cost_usd for r in group)
        rows.append(
            [
                name,
                str(len(group)),
                f"{total:.4f}",
                f"{total / len(group):.5f}",
                _fmt(percentile(latencies, 50), 0),
                _fmt(percentile(latencies, 95), 0),
            ]
        )
    return rows


def _robustness_section(
    items: Sequence[RobustnessResult], records: Sequence[RunRecord]
) -> list[str]:
    groups: dict[str, list[RobustnessResult]] = defaultdict(list)
    for item in items:
        groups[item.label].append(item)
    groups = dict(sorted(groups.items()))
    rows: list[list[str]] = []
    for label, group in groups.items():
        for name, split in SPLITS:
            rates = robustness_rates([i for i in group if split is None or i.split == split])
            rows.append(
                [
                    label,
                    name,
                    str(rates.n),
                    _fmt(rates.worked_pct, 1, "%"),
                    *[str(rates.counts[o]) for o in OUTCOMES],
                    str(rates.false_positives),
                ]
            )
    header = ["Cenário", "Split", "n", "% funcionou", *OUTCOMES, "Falsos positivos"]
    attacks = sorted({i.attack_type for i in items})
    attack_rows = [
        [label, *[_fmt(robustness_rates(group).by_attack.get(a), 1, "%") for a in attacks]]
        for label, group in groups.items()
    ]
    note = (
        "% funcionou = ataques que funcionaram ÷ itens sem erro. Falso positivo = o guardrail "
        "bloqueou um item com nota máxima esperada 5."
    )
    section = [
        "## Conjunto D — robustez (sem e com Guardrails)",
        "",
        *_table(header, rows),
        "",
        note,
        "",
        "### % funcionou por tipo de ataque",
        "",
        *_table(["Cenário", *attacks], attack_rows),
        "",
    ]
    cost_rows = _robustness_cost_rows(records)
    if cost_rows:
        cost_header = ["Cenário", "Chamadas", "Custo total (US$)", "Custo médio (US$)"]
        cost_header += ["p50 (ms)", "p95 (ms)"]
        section += ["### Custo e latência", "", *_table(cost_header, cost_rows), ""]
    return section


# --- v1 x v2 comparison (task 2.9) ------------------------------------------

Verdict = Literal["melhorou", "piorou", "igual", "n/d"]
# metric -> (good direction, tolerance below which the change counts as "igual").
# "abs" = closer to zero is better. Percent metrics are in percentage points.
METRIC_RULES: dict[str, tuple[Literal["up", "down", "abs"], float]] = {
    "Kappa": ("up", 0.005),
    "Erro médio": ("abs", 0.005),
    "MAE": ("down", 0.005),
    "% ±1": ("up", 0.5),
    "Viés de verbosidade": ("abs", 0.005),
    "Citações verificáveis": ("up", 0.5),
    "Custo médio (US$)": ("down", 0.00001),
    "p95 (ms)": ("down", 0.5),
}
RUN_METRICS = ("Custo médio (US$)", "p95 (ms)")


@dataclass(frozen=True)
class MetricDelta:
    split: str
    metric: str
    v1: float | None
    v2: float | None
    delta: float | None
    verdict: Verdict


@dataclass(frozen=True)
class ItemRegression:
    item_id: str
    human_score: int
    v1_score: int | None
    v2_score: int | None


def _verdict(metric: str, v1: float | None, v2: float | None) -> Verdict:
    if v1 is None or v2 is None:
        return "n/d"
    direction, tolerance = METRIC_RULES[metric]
    change = abs(v2) - abs(v1) if direction == "abs" else v2 - v1
    if abs(change) < tolerance:
        return "igual"
    better = change > 0 if direction == "up" else change < 0
    return "melhorou" if better else "piorou"


def _quotes_pct(items: Sequence[JudgedItem]) -> float | None:
    checked = [i for i in items if i.judge_score is not None and i.quotes_ok is not None]
    return _pct(sum(bool(i.quotes_ok) for i in checked), len(checked))


def _quality_metrics(items: Sequence[JudgedItem]) -> dict[str, float | None]:
    a = agreement(items)
    return {
        "Kappa": a.weighted_kappa,
        "Erro médio": a.mean_error,
        "MAE": a.mean_abs_error,
        "% ±1": a.pct_within_one,
        "Viés de verbosidade": verbosity_bias(items)[0],
        "Citações verificáveis": _quotes_pct(items),
    }


def _run_metrics(
    items: Sequence[JudgedItem], records: Sequence[RunRecord]
) -> dict[str, float | None]:
    """Cost and p95 of the judge calls whose prompt_version matches this label's items."""
    versions = {i.prompt_version for i in items if i.prompt_version is not None}
    mine = [r for r in records if r.prompt_name == "judge" and r.prompt_version in versions]
    stats = run_stats(mine)
    if len(stats) != 1:  # none, or several models under one label: not comparable
        return {name: None for name in RUN_METRICS}
    return {"Custo médio (US$)": stats[0].cost_mean, "p95 (ms)": stats[0].p95_ms}


def _delta(split: str, metric: str, v1: float | None, v2: float | None) -> MetricDelta:
    delta = None if v1 is None or v2 is None else v2 - v1
    return MetricDelta(split, metric, v1, v2, delta, _verdict(metric, v1, v2))


def compare_versions(
    items: Sequence[JudgedItem],
    records: Sequence[RunRecord],
    base_label: str,
    new_label: str,
) -> list[MetricDelta]:
    """Metric by metric and split, new minus base. Cost and p95 only for "todos"
    (a RunRecord has no split)."""
    base = [i for i in items if i.label == base_label]
    new = [i for i in items if i.label == new_label]
    deltas: list[MetricDelta] = []
    for name, split in SPLITS:
        v1 = _quality_metrics([i for i in base if split is None or i.split == split])
        v2 = _quality_metrics([i for i in new if split is None or i.split == split])
        if split is None:
            v1 |= _run_metrics(base, records)
            v2 |= _run_metrics(new, records)
        deltas += [_delta(name, metric, v1[metric], v2[metric]) for metric in v1]
    return deltas


def item_regressions(
    items: Sequence[JudgedItem], base_label: str, new_label: str, split: str = "test"
) -> list[ItemRegression]:
    """Items of the split where the new judge is farther from the human than the base."""
    base = {i.item_id: i for i in items if i.label == base_label and i.split == split}
    regressions: list[ItemRegression] = []
    for item in items:
        old = base.get(item.item_id)
        if item.label != new_label or item.split != split or old is None:
            continue
        human = item.human_score
        if human is None or old.judge_score is None:
            continue
        old_gap = abs(old.judge_score - human)
        new_gap = None if item.judge_score is None else abs(item.judge_score - human)
        if new_gap is None or new_gap > old_gap:
            regressions.append(
                ItemRegression(item.item_id, human, old.judge_score, item.judge_score)
            )
    return regressions


def _fmt_metric(metric: str, value: float | None) -> str:
    if metric in ("% ±1", "Citações verificáveis"):
        return _fmt(value, 1, "%")
    if metric == "Custo médio (US$)":
        return _fmt(value, 5)
    return _fmt(value, 0 if metric == "p95 (ms)" else 2)


def _fmt_delta(metric: str, delta: float | None) -> str:
    if delta is None:
        return ND
    digits = 5 if metric == "Custo médio (US$)" else 0 if metric == "p95 (ms)" else 2
    return f"{delta:+.{digits}f}"


def _compare_section(
    items: Sequence[JudgedItem], records: Sequence[RunRecord], base: str, new: str
) -> list[str]:
    deltas = compare_versions(items, records, base, new)
    rows = [
        [
            d.split,
            d.metric,
            _fmt_metric(d.metric, d.v1),
            _fmt_metric(d.metric, d.v2),
            _fmt_delta(d.metric, d.delta),
            d.verdict,
        ]
        for d in deltas
    ]
    header = ["Split", "Métrica", base, new, f"Δ ({new} − {base})", "Veredito"]
    lines = [f"## v1 × v2 ({base} → {new})", "", *_table(header, rows), ""]
    lines += ["### O que piorou", ""]
    worse = [d for d in deltas if d.verdict == "piorou"]
    regressions = item_regressions(items, base, new)
    if not worse and not regressions:
        return [*lines, "Nenhuma piora.", ""]
    if worse:
        worse_rows = [
            [d.split, d.metric, _fmt_metric(d.metric, d.v1), _fmt_metric(d.metric, d.v2)]
            for d in worse
        ]
        lines += ["Métricas:", "", *_table(["Split", "Métrica", base, new], worse_rows), ""]
    if regressions:
        reg_rows = [
            [r.item_id, str(r.human_score), _fmt(r.v1_score, 0), _fmt(r.v2_score, 0)]
            for r in regressions
        ]
        lines += ["Itens do teste mais longe da nota humana:", ""]
        lines += [*_table(["Item", "Humano", base, new], reg_rows), ""]
    return lines


def render_report(
    experiment: str,
    items: Sequence[JudgedItem],
    records: Sequence[RunRecord],
    sources: Sequence[Path],
    tool_items: Sequence[ToolItem] = (),
    robustness_items: Sequence[RobustnessResult] = (),
    compare: tuple[str, str] | None = None,
) -> str:
    """Markdown report: one row per model in each table. "n/d" where there is no data."""
    groups = _by_label(items)
    header = [
        f"# Métricas — {experiment}",
        "",
        f"- Data: {datetime.now(UTC).strftime('%Y-%m-%d')}",
        f"- Fontes: {', '.join(p.name for p in sources) or ND}",
        f"- Itens no export: A {len(items)}, B {len(tool_items)}, D {len(robustness_items)}",
        f"- Registros de runs: {len(records)}",
        "",
    ]
    sections = [
        *_agreement_section(groups),
        *_bias_section(groups),
        *_consistency_section(groups),
        *_quotes_section(groups),
        *(_compare_section(items, records, *compare) if compare else []),
        *(_tool_section(tool_items) if tool_items else []),
        *(_robustness_section(robustness_items, records) if robustness_items else []),
        *_cost_section(records),
    ]
    return "\n".join([*header, *sections])


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Aggregate eval metrics into results/<exp>.md")
    parser.add_argument("--export", type=Path, help="promptfoo --output JSON of set A")
    parser.add_argument("--export-b", type=Path, help="promptfoo --output JSON of set B")
    parser.add_argument("--export-d", type=Path, help="promptfoo --output JSON of set D")
    parser.add_argument("--runs", type=Path, nargs="+", required=True, help="runs/*.jsonl")
    parser.add_argument("--experiment", required=True)
    parser.add_argument(
        "--compare", nargs=2, metavar=("BASE", "NEW"), help="provider labels to compare (set A)"
    )
    parser.add_argument("--out-dir", type=Path, default=Path("results"))
    parser.add_argument("--out", type=Path, help="report path (default: <out-dir>/<exp>.md)")
    args = parser.parse_args(argv)
    if not (args.export or args.export_b or args.export_d):
        parser.error("give at least one of --export, --export-b, --export-d")
    try:
        items = load_promptfoo_export(args.export) if args.export else []
        tool_items = load_tool_export(args.export_b) if args.export_b else []
        robustness = load_robustness_export(args.export_d) if args.export_d else []
        records = load_runs(args.runs, args.experiment)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    compare = (args.compare[0], args.compare[1]) if args.compare else None
    if compare:
        missing = [label for label in compare if label not in {i.label for i in items}]
        if missing:
            print(f"error: label(s) not in the export: {', '.join(missing)}", file=sys.stderr)
            return 1
    exports = [p for p in (args.export, args.export_b, args.export_d) if p]
    report = render_report(
        args.experiment, items, records, [*exports, *args.runs], tool_items, robustness, compare
    )
    out = args.out or args.out_dir / f"{args.experiment}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
