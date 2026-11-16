"""Promptfoo Python provider for set A (judge).

Thin on purpose: call_api reads the Promptfoo config and vars, rebuilds the GoldenItem
and delegates to run_item, which calls the real mia.judge (never a copy of the prompt).
"""

from pathlib import Path
from typing import Any, Final

from langchain_core.language_models import BaseChatModel

from mia.judge import JUDGE_PROMPT, judge_answer
from mia.llm import DEFAULT_RUNS_DIR, load_models_config
from mia.prompts import load_prompt, resolve_prompt_model
from mia.schemas import GoldenItem

DEFAULT_EXPERIMENT: Final = "promptfoo_set_a"


def _model_used(model: str | None) -> str:
    """The model ref the judge will run on: explicit config > prompt_models.judge."""
    spec = resolve_prompt_model(load_prompt(*JUDGE_PROMPT), load_models_config(), model)
    return spec.ref


def run_item(
    item: GoldenItem,
    *,
    model: str | None,
    experiment: str,
    runs_dir: Path = DEFAULT_RUNS_DIR,
    chat_model: BaseChatModel | None = None,
) -> dict[str, Any]:
    """Judge one golden item. Errors become {"error": ...} so only this case fails."""
    try:
        score = judge_answer(
            item.question,
            item.answer_text,
            model=model,
            experiment=experiment,
            runs_dir=runs_dir,
            chat_model=chat_model,
        )
        used = _model_used(model)
    except Exception as exc:  # noqa: BLE001 - one bad item must not stop the whole eval
        return {"error": f"{type(exc).__name__}: {exc}"}
    return {
        "output": score.model_dump_json(),
        "metadata": {
            "item_id": item.item_id,
            "variant": item.variant,
            "split": item.split,
            "human_score": item.human_score,
            "model": used,
        },
    }


def _item_from_vars(context: dict[str, Any]) -> GoldenItem:
    raw = context["vars"]["item"]
    if isinstance(raw, str):
        return GoldenItem.model_validate_json(raw)
    return GoldenItem.model_validate(raw)


def call_api(prompt: str, options: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Promptfoo entry point. ``prompt`` is only a marker; the real prompt is prompts/judge."""
    config = options.get("config") or {}
    try:
        item = _item_from_vars(context)
    except (KeyError, ValueError) as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
    return run_item(
        item,
        model=config.get("model"),
        experiment=config.get("experiment", DEFAULT_EXPERIMENT),
    )
