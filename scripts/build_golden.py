"""Task 2.2: generate the 70 golden set A answers (10 questions x 7 variants).

Usage:
    uv run --env-file .env python scripts/build_golden.py [--force]

Output: evals/datasets/judge_golden.jsonl (one GoldenItem per line, without human_score/split).
Exit codes: 0 ok, 1 failure (nothing written), 2 model configuration error.
Everything is generated in memory and written only at the end, so a failure leaves no partial file.
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final, get_args

import yaml
from langchain_core.language_models import BaseChatModel

from mia.cases import CASES_DIR, CaseError, load_case_texts
from mia.llm import DEFAULT_RUNS_DIR, LLMInvalidOutputError, ModelConfigError, load_models_config
from mia.pii import mask_cv
from mia.prompts import PromptError, load_prompt, resolve_prompt_model, run_prompt
from mia.schemas import GoldenItem, Question, Variant

REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
QUESTIONS_PATH: Final[Path] = REPO_ROOT / "evals" / "datasets" / "questions.yaml"
OUTPUT_PATH: Final[Path] = REPO_ROOT / "evals" / "datasets" / "judge_golden.jsonl"
EXPERIMENT: Final = "golden-2.2"
PROMPT_NAME: Final = "synthetic_candidate"
PROMPT_VERSION: Final = 4

# question_id -> case_id: the case whose CV gives the candidate's background (2 per case).
QUESTION_CASE: Final[dict[str, str]] = {
    "gq-tech-01": "prompt-engineer-jr",
    "gq-tech-02": "prompt-engineer-jr",
    "gq-tech-03": "data-analyst-pleno",
    "gq-tech-04": "data-analyst-pleno",
    "gq-tech-05": "ai-product-manager",
    "gq-beh-01": "ai-product-manager",
    "gq-tech-06": "backend-python-jr",
    "gq-beh-02": "backend-python-jr",
    "gq-beh-03": "software-intern",
    "gq-beh-04": "software-intern",
}

# Generation order: the paraphrase needs the level_3 answer, so level_3 comes first.
VARIANTS: Final[tuple[Variant, ...]] = get_args(Variant)

# variant -> (target_score, style): the prompt variables that steer the answer quality.
TARGETS: Final[dict[Variant, tuple[str, str]]] = {
    "level_5": ("5", "direto, concreto e detalhado"),
    "level_4": ("4", "claro, com exemplo e resultado, mas sem reflexão profunda"),
    "level_3": ("3", "simples, com um exemplo raso"),
    "level_2": ("2", "vago e genérico, quase sem exemplo"),
    "level_1": ("1", "fora do tema, sem relação com a pergunta"),
    "rambling": ("enrolada", "prolixo, longo e repetitivo, sem nenhum fato concreto"),
    "paraphrase": ("paráfrase", "mesmo conteúdo da resposta base, com outras palavras"),
}


class GoldenBuildError(Exception):
    """The golden set cannot be built; the message says why (item id, file, ...)."""


def load_questions(path: Path = QUESTIONS_PATH) -> list[Question]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [Question.model_validate(item) for item in data["questions"]]


def item_id(question: Question, variant: Variant) -> str:
    return f"{question.id}-{variant}"


def generate_answer(
    question: Question,
    variant: Variant,
    cv_masked: str,
    *,
    chat_model: BaseChatModel | None = None,
    base_answer: str | None = None,
    runs_dir: Path = DEFAULT_RUNS_DIR,
) -> str:
    """One answer for (question, variant). base_answer is only used by the paraphrase."""
    target, style = TARGETS[variant]
    text = run_prompt(
        load_prompt(PROMPT_NAME, PROMPT_VERSION),
        {
            "target_score": target,
            "style": style,
            "question": question.text,
            "cv": cv_masked,
            "base_answer": base_answer or "",
        },
        experiment=EXPERIMENT,
        runs_dir=runs_dir,
        chat_model=chat_model,
    ).strip()
    if not text:
        raise GoldenBuildError(f"{item_id(question, variant)}: o modelo devolveu resposta vazia")
    return text


def _question_items(
    question: Question, cv_masked: str, generated_by: str, **kwargs: object
) -> list[GoldenItem]:
    items: list[GoldenItem] = []
    answers: dict[Variant, str] = {}
    for variant in VARIANTS:
        is_paraphrase = variant == "paraphrase"
        answers[variant] = generate_answer(
            question,
            variant,
            cv_masked,
            base_answer=answers["level_3"] if is_paraphrase else None,
            **kwargs,  # type: ignore[arg-type]
        )
        items.append(
            GoldenItem(
                item_id=item_id(question, variant),
                question=question,
                answer_text=answers[variant],
                variant=variant,
                paraphrase_of=item_id(question, "level_3") if is_paraphrase else None,
                generated_by=generated_by,
            )
        )
    return items


def build_items(
    questions: list[Question],
    *,
    chat_model: BaseChatModel | None = None,
    cases_dir: Path = CASES_DIR,
    runs_dir: Path = DEFAULT_RUNS_DIR,
) -> list[GoldenItem]:
    """All items for the questions, in memory. Raises GoldenBuildError on the first problem."""
    prompt = load_prompt(PROMPT_NAME, PROMPT_VERSION)
    spec = resolve_prompt_model(prompt, load_models_config())
    generated_by = f"{spec.ref}|{PROMPT_NAME}@v{prompt.version}"
    items: list[GoldenItem] = []
    for question in questions:
        case_id = QUESTION_CASE.get(question.id)
        if case_id is None:
            raise GoldenBuildError(f"{question.id}: pergunta sem caso em QUESTION_CASE")
        cv_text, _ = load_case_texts(case_id, cases_dir)
        items += _question_items(
            question,
            mask_cv(cv_text),
            generated_by,
            chat_model=chat_model,
            runs_dir=runs_dir,
        )
    return items


def write_jsonl(items: list[GoldenItem], path: Path, *, force: bool) -> None:
    if path.exists() and not force:
        raise GoldenBuildError(f"{path} já existe; use --force para sobrescrever")
    lines = [item.model_dump_json() for item in items]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None, *, chat_model: BaseChatModel | None = None) -> int:
    parser = argparse.ArgumentParser(prog="build_golden", description="Build golden set A answers")
    parser.add_argument("--force", action="store_true", help="overwrite the output file")
    args = parser.parse_args(argv)
    try:
        if OUTPUT_PATH.exists() and not args.force:
            # Fail before spending any model call.
            raise GoldenBuildError(f"{OUTPUT_PATH} já existe; use --force para sobrescrever")
        items = build_items(
            load_questions(QUESTIONS_PATH),
            chat_model=chat_model,
            cases_dir=CASES_DIR,
            runs_dir=DEFAULT_RUNS_DIR,
        )
        write_jsonl(items, OUTPUT_PATH, force=args.force)
    except ModelConfigError as exc:
        print(f"configuração do modelo: {exc}", file=sys.stderr)
        return 2
    except (GoldenBuildError, PromptError, LLMInvalidOutputError, CaseError) as exc:
        print(f"falhou, nada gravado: {exc}", file=sys.stderr)
        return 1
    print(f"{len(items)} itens gravados em {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
