"""Set A regression: replay the recorded judge answers offline (task 2.10, step 2).

No network, no .env: the fake model returns the outputs saved in the cassette fixture, so
only the code that decides (parse, schema, literal quotes, metrics) can cause a failure.
If a change is legitimate, re-record the fixture in the same commit:
    uv run python scripts/record_judge_cassette.py --runs runs/<file>.jsonl --experiment <name>
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from mia.schemas import AnswerScore, GoldenItem

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "judge_cassette_set_a.jsonl"
REGRAVE = "regrave o fixture: uv run python scripts/record_judge_cassette.py"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


rec = _load("record_judge_cassette", ROOT / "scripts" / "record_judge_cassette.py")
asserts = _load("judge_asserts", ROOT / "evals" / "assertions" / "judge_asserts.py")


def check_cassette_items(items: list[GoldenItem], recorded: list[object]) -> None:
    """Fail when the fixture and the golden set no longer list the same items."""
    golden_ids = {i.item_id for i in items}
    fixture_ids = {r.item_id for r in recorded}  # type: ignore[attr-defined]
    if golden_ids != fixture_ids:
        missing = sorted(golden_ids - fixture_ids)
        extra = sorted(fixture_ids - golden_ids)
        pytest.fail(f"golden e fixture divergem (faltam {missing}, sobram {extra}); {REGRAVE}")


def check_metrics(
    header: object, kappa: float | None, within_one: float | None, quotes: float | None
) -> list[str]:
    """Names of the metrics that fell below the reference saved in the header (tolerance 0)."""
    current = {"kappa": kappa, "within_one_pct": within_one, "quotes_verified_pct": quotes}
    failures = []
    for name, value in current.items():
        reference = getattr(header, name)
        if reference is not None and (value is None or value < reference):
            failures.append(f"{name}: {value} < referência {reference}")
    return failures


def _score_context(item: GoldenItem) -> dict[str, object]:
    return {"vars": {"item": {"item_id": item.item_id, "human_score": item.human_score}}}


def _replay_all(
    items: list[GoldenItem], recorded: list[object], runs_dir: Path, version: int
) -> dict[str, AnswerScore]:
    outputs = {r.item_id: r.output for r in recorded}  # type: ignore[attr-defined]
    scores: dict[str, AnswerScore] = {}
    for item in items:
        try:
            scores[item.item_id] = rec.replay_item(
                item, outputs[item.item_id], runs_dir, prompt_version=version
            )
        except Exception as exc:  # noqa: BLE001 - report which item broke
            pytest.fail(f"{item.item_id}: sem AnswerScore válido ({exc!r})")
    return scores


def test_set_a_replay_matches_reference_metrics(tmp_path: Path) -> None:
    header, recorded = rec.load_cassette(FIXTURE)
    items = rec.load_golden()
    check_cassette_items(items, recorded)

    scores = _replay_all(items, recorded, tmp_path, header.prompt_version)
    assert len(scores) == len(items) == 70

    # The three set A assertions, on the judge output re-serialized from the validated score.
    within_one_ok = 0
    for item in items:
        output = scores[item.item_id].model_dump_json()
        context = _score_context(item)
        assert asserts.assert_schema(output, context)["pass"], item.item_id
        within_one_ok += asserts.assert_score_within_one(output, context)["pass"]
    quotes_ok = sum(
        asserts.assert_quotes_verified(s.model_dump_json(), {})["pass"] for s in scores.values()
    )

    kappa, within_one, quotes = rec.reference_metrics(items, scores)
    assert within_one == pytest.approx(100 * within_one_ok / len(items))
    assert quotes == pytest.approx(100 * quotes_ok / len(items))
    assert check_metrics(header, kappa, within_one, quotes) == [], REGRAVE
    # Replay is deterministic: with tolerance 0 the numbers must also not drift upwards.
    assert (kappa, within_one, quotes) == pytest.approx(
        (header.kappa, header.within_one_pct, header.quotes_verified_pct)
    )


def test_replay_writes_only_to_the_temporary_runs_dir(tmp_path: Path) -> None:
    header, recorded = rec.load_cassette(FIXTURE)
    items = rec.load_golden()[:1]
    real_runs = ROOT / "runs"
    before = sorted(p.name for p in real_runs.glob("*")) if real_runs.exists() else []

    _replay_all(items, recorded, tmp_path, header.prompt_version)

    after = sorted(p.name for p in real_runs.glob("*")) if real_runs.exists() else []
    assert before == after
    assert list(tmp_path.glob("*.jsonl"))


def test_invalid_output_reports_the_item_id(tmp_path: Path) -> None:
    items = rec.load_golden()[:1]
    broken = [rec.CassetteItem(item_id=items[0].item_id, output="não é json")]
    with pytest.raises(pytest.fail.Exception, match=items[0].item_id):
        _replay_all(items, broken, tmp_path, 1)


def test_metric_above_reference_is_reported_by_name() -> None:
    header = rec.CassetteHeader(
        prompt_version=1,
        source_run="x",
        model="m",
        kappa=0.5,
        within_one_pct=80.0,
        quotes_verified_pct=60.0,
    )
    failures = check_metrics(header, 0.5, 72.0, 65.0)
    assert len(failures) == 1
    assert failures[0].startswith("within_one_pct")
    assert check_metrics(header, 0.6, 80.0, 60.0) == []


def test_fixture_missing_a_golden_item_asks_to_rerecord() -> None:
    _, recorded = rec.load_cassette(FIXTURE)
    items = rec.load_golden()
    with pytest.raises(pytest.fail.Exception, match="regrave o fixture"):
        check_cassette_items(items, recorded[1:])
