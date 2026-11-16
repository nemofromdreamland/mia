"""Task 2.10: record the judge's answers for set A into a versioned test fixture.

Usage:
    uv run python scripts/record_judge_cassette.py --runs runs/<file>.jsonl \
        --experiment judge_v1_vs_v2 [--prompt-version 1] [--out <file>]

Reads RunRecords already saved in runs/ (no model calls) and writes one line per golden item
with the raw model output, plus a header with reference metrics computed by replaying the
real judge code on those outputs. tests/test_eval_regression.py replays the fixture offline.
Exit codes: 0 ok, 1 an item has no record or more than one (nothing is written).
"""

import argparse
import importlib.util
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType
from typing import Final

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from pydantic import BaseModel

from mia.judge import JUDGE_PROMPT, judge_answer
from mia.pii import mask_text
from mia.schemas import AnswerScore, GoldenItem, RunRecord

ROOT: Final = Path(__file__).resolve().parents[1]
GOLDEN_PATH: Final = ROOT / "evals" / "datasets" / "judge_golden.jsonl"
DEFAULT_OUT: Final = ROOT / "tests" / "fixtures" / "judge_cassette_set_a.jsonl"


class CassetteItem(BaseModel):
    item_id: str
    output: str  # output_raw of the single RunRecord (already the repaired text, if any)


class CassetteHeader(BaseModel):
    prompt_version: int
    source_run: str
    model: str
    kappa: float | None
    within_one_pct: float | None
    quotes_verified_pct: float | None


def load_metrics() -> ModuleType:
    """Import evals/metrics.py by path (evals/ is not a package)."""
    spec = importlib.util.spec_from_file_location("eval_metrics", ROOT / "evals" / "metrics.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["eval_metrics"] = module
    spec.loader.exec_module(module)
    return module


def load_golden(path: Path | None = None) -> list[GoldenItem]:
    lines = (path or GOLDEN_PATH).read_text(encoding="utf-8").splitlines()
    return [GoldenItem.model_validate_json(line) for line in lines if line.strip()]


def load_cassette(path: Path) -> tuple[CassetteHeader, list[CassetteItem]]:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    header = CassetteHeader.model_validate_json(lines[0])
    return header, [CassetteItem.model_validate_json(line) for line in lines[1:]]


def match_records(
    items: Sequence[GoldenItem], records: Sequence[RunRecord], *, prompt_version: int
) -> dict[str, list[RunRecord]]:
    """Records of the judge at prompt_version per item_id, matched by question + masked answer."""
    by_key: dict[tuple[object, object], list[RunRecord]] = {}
    for record in records:
        if record.prompt_name == JUDGE_PROMPT[0] and record.prompt_version == prompt_version:
            key = (record.input.get("question"), record.input.get("answer"))
            by_key.setdefault(key, []).append(record)
    return {
        item.item_id: by_key.get((item.question.text, mask_text(item.answer_text)), [])
        for item in items
    }


def replay_item(
    item: GoldenItem, output: str, runs_dir: Path, *, prompt_version: int
) -> AnswerScore:
    """Run the real judge on a fake model that returns the recorded output (no network)."""
    fake = GenericFakeChatModel(messages=iter([AIMessage(content=output)]))
    return judge_answer(
        item.question,
        item.answer_text,
        chat_model=fake,
        runs_dir=runs_dir,
        experiment="cassette_replay",
        prompt_version=prompt_version,
    )


def reference_metrics(
    items: Sequence[GoldenItem], scores: dict[str, AnswerScore]
) -> tuple[float | None, float | None, float | None]:
    """(kappa, % within one, % verified quotes) for the replayed scores."""
    metrics = load_metrics()
    judged = [
        metrics.JudgedItem(
            item_id=i.item_id,
            label="cassette",
            variant=i.variant,
            split=i.split,
            paraphrase_of=i.paraphrase_of,
            human_score=i.human_score,
            judge_score=scores[i.item_id].score,
            quotes_ok=scores[i.item_id].quotes_verified,
        )
        for i in items
    ]
    agree = metrics.agreement(judged)
    checked = [j.quotes_ok for j in judged if j.quotes_ok is not None]
    quotes = 100 * sum(checked) / len(checked) if checked else None
    return agree.weighted_kappa, agree.pct_within_one, quotes


def _problems(matched: dict[str, list[RunRecord]]) -> list[str]:
    return [f"{k}: {len(v)} records" for k, v in matched.items() if len(v) != 1]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--prompt-version", type=int, default=JUDGE_PROMPT[1])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    metrics = load_metrics()
    records = metrics.load_runs([args.runs], args.experiment)
    items = load_golden()
    matched = match_records(items, records, prompt_version=args.prompt_version)
    problems = _problems(matched)
    if problems:
        print("Each golden item needs exactly one record:", file=sys.stderr)
        print("\n".join(problems), file=sys.stderr)
        return 1

    outputs = {item_id: recs[0].output_raw for item_id, recs in matched.items()}
    with tempfile.TemporaryDirectory() as tmp:
        scores = {
            i.item_id: replay_item(
                i, outputs[i.item_id], Path(tmp), prompt_version=args.prompt_version
            )
            for i in items
        }
    kappa, within_one, quotes = reference_metrics(items, scores)
    model = next(iter(matched.values()))[0].model
    header = CassetteHeader(
        prompt_version=args.prompt_version,
        source_run=args.runs.name,
        model=model,
        kappa=kappa,
        within_one_pct=within_one,
        quotes_verified_pct=quotes,
    )
    lines = [header.model_dump_json()]
    lines += [
        CassetteItem(item_id=i.item_id, output=outputs[i.item_id]).model_dump_json() for i in items
    ]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {len(items)} items to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
