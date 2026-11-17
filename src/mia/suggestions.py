"""Answer suggestions (spec 5.6): a strong and a weak answer for one interviewer line.

Plan questions use the pre-generated cases/<id>/examples.json. Follow-ups are written at runtime,
so their suggestions are generated on demand with `synthetic_candidate` on Nova 2 Lite (Bedrock,
another model family than the Claude judge; the container has no Groq key) and cached per
(session, turn). Suggestions never reach the judge.
"""

from collections.abc import Callable
from pathlib import Path

from mia.cases import CASES_DIR, load_case_texts
from mia.pii import mask_cv
from mia.prompts import available_versions, load_prompt, run_prompt
from mia.schemas import AnswerExample

PROMPT_NAME = "synthetic_candidate"
RUNTIME_MODEL = "bedrock:us.amazon.nova-2-lite-v1:0"
STRONG = ("5", "direto, concreto, com um exemplo e um resultado; no máximo 80 palavras")
WEAK = ("2", "vago e genérico, quase sem exemplo; no máximo 40 palavras")

# (case_id, question_id, interviewer_text, cache_key) -> AnswerExample
Suggest = Callable[[str, str, str, str], AnswerExample]


def generate_answer(
    question_text: str, cv_masked: str, target: tuple[str, str], model: str | None = None
) -> str:
    prompt = load_prompt(PROMPT_NAME, max(available_versions(PROMPT_NAME)))
    variables = {
        "target_score": target[0],
        "style": target[1],
        "question": question_text,
        "base_answer": "",
        "cv": cv_masked,
    }
    return run_prompt(prompt, variables, model=model, experiment="suggestions-5.6").strip()


def model_suggest(cases_dir: Path = CASES_DIR) -> Suggest:
    """Runtime suggester with an in-process cache (one generation per follow-up turn)."""
    cache: dict[str, AnswerExample] = {}

    def suggest(case_id: str, question_id: str, text: str, key: str) -> AnswerExample:
        if key not in cache:
            cv_masked = mask_cv(load_case_texts(case_id, cases_dir)[0])
            cache[key] = AnswerExample(
                question_id=question_id,
                strong=generate_answer(text, cv_masked, STRONG, RUNTIME_MODEL),
                weak=generate_answer(text, cv_masked, WEAK, RUNTIME_MODEL),
            )
        return cache[key]

    return suggest
