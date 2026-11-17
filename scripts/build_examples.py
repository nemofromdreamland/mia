"""Spec 5.6: generate a strong and a weak example answer for each question of every case.

Usage:
    uv run python scripts/build_examples.py [--case <case_id>]

Uses `synthetic_candidate` (Groq, another model family than the judge) with the same targets
as the golden set: level 5 ("direto, concreto e detalhado") and level 2 (vague). The output goes
to cases/<id>/examples.json; the case `version` must then be bumped by hand.
"""

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from mia.cases import CASES_DIR, EXAMPLES_FILE, list_cases, load_case, load_case_texts
from mia.interviewer import shorten_plan
from mia.llm import load_models_config
from mia.pii import mask_cv
from mia.prompts import available_versions, load_prompt, resolve_prompt_model, run_prompt
from mia.schemas import AnswerExample, CaseExamples, Question

PROMPT_NAME = "synthetic_candidate"
EXPERIMENT = "examples-5.6"
# Short answers: they are read on screen (and aloud in voice mode).
STRONG = ("5", "direto, concreto, com um exemplo e um resultado; no máximo 80 palavras")
WEAK = ("2", "vago e genérico, quase sem exemplo; no máximo 40 palavras")

Generate = Callable[[Question, str, tuple[str, str]], str]


def model_generate(question: Question, cv_masked: str, target: tuple[str, str]) -> str:
    prompt = load_prompt(PROMPT_NAME, max(available_versions(PROMPT_NAME)))
    text = run_prompt(
        prompt,
        {
            "target_score": target[0],
            "style": target[1],
            "question": question.text,
            "base_answer": "",
            "cv": cv_masked,
        },
        experiment=EXPERIMENT,
    )
    return text.strip()


def build_case(case_id: str, generate: Generate, cases_dir: Path = CASES_DIR) -> CaseExamples:
    plan = shorten_plan(load_case(case_id, cases_dir).plan)
    cv_masked = mask_cv(load_case_texts(case_id, cases_dir)[0])
    prompt = load_prompt(PROMPT_NAME, max(available_versions(PROMPT_NAME)))
    model = resolve_prompt_model(prompt, load_models_config()).ref
    examples = [
        AnswerExample(
            question_id=q.id,
            strong=generate(q, cv_masked, STRONG),
            weak=generate(q, cv_masked, WEAK),
        )
        for q in plan.questions
    ]
    return CaseExamples(
        case_id=case_id, generated_by=f"{PROMPT_NAME}@v{prompt.version} {model}", examples=examples
    )


def write(examples: CaseExamples, cases_dir: Path = CASES_DIR) -> Path:
    path = cases_dir / examples.case_id / EXAMPLES_FILE
    data = examples.model_dump()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main(argv: Sequence[str] | None = None, generate: Generate = model_generate) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--case", help="só este caso")
    args = parser.parse_args(argv)
    ids = [args.case] if args.case else [c.case_id for c in list_cases()]
    for case_id in ids:
        path = write(build_case(case_id, generate))
        print(f"OK: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
