"""Task 1.12: generate screening.json and plan.json of the demo cases with the real prep.

Usage:
    uv run --env-file .env python scripts/build_cases.py [--case <id> ...] [--model <name>]

Exit codes: 0 all cases built, 1 some case failed (nothing written for it),
2 model configuration error. The script never changes `version` in case.yaml.
"""

import argparse
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from mia.cases import CASES_DIR, CaseError, list_cases, load_case_texts, write_fixtures
from mia.llm import LLMInvalidOutputError, ModelConfigError
from mia.prep_graph import PrepError, PrepInput, PrepResult, run_prep
from mia.schemas import Case

Prep = Callable[[PrepInput], PrepResult]


def build_one(case: Case, cases_dir: Path, prep: Prep) -> None:
    """Run the prep for one case; write the files only if it succeeds."""
    _, job_text = load_case_texts(case.case_id, cases_dir)
    data = PrepInput(
        cv_path=cases_dir / case.case_id / "cv.md",
        job_text=job_text,
        persona=case.persona,
        level=case.level,
        estimated_minutes=case.estimated_minutes,
        language=case.language,
    )
    write_fixtures(case.case_id, prep(data), cases_dir)


def _parse(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="build_cases", description="Build case fixtures")
    parser.add_argument("--case", action="append", dest="cases", help="case id (repeatable)")
    parser.add_argument("--model", default=None, help="model for the prep (default: models.yaml)")
    return parser.parse_args(argv)


def main(
    argv: Sequence[str] | None = None,
    prep: Prep | None = None,
    cases_dir: Path = CASES_DIR,
) -> int:
    args = _parse(argv)
    run = prep or (lambda data: run_prep(data, model=args.model))
    available = {case.case_id: case for case in list_cases(cases_dir)}
    wanted = args.cases or list(available)
    failed = False
    for case_id in wanted:
        case = available.get(case_id)
        if case is None:
            print(f"{case_id}: caso não encontrado", file=sys.stderr)
            failed = True
            continue
        try:
            build_one(case, cases_dir, run)
        except ModelConfigError as exc:
            print(f"{case_id}: configuração do modelo: {exc}", file=sys.stderr)
            return 2
        except (PrepError, LLMInvalidOutputError, CaseError) as exc:
            print(f"{case_id}: falhou, nada gravado: {exc}", file=sys.stderr)
            failed = True
            continue
        print(f"{case_id}: screening.json e plan.json gravados")
    print(
        "Revise os JSON gerados. Se cv, vaga ou plano mudaram, "
        "suba `version` no case.yaml (o script não altera)."
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
