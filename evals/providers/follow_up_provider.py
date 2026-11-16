"""Promptfoo Python provider for set B (follow_up tool decision).

Thin on purpose: call_api rebuilds the ToolMomentItem and the Question, then run_tool_item
calls the real mia.interviewer.should_follow_up (never a copy of the prompt). The item's
history arrives as text, so it is turned back into Turns (spec 2.7, P3a) and interviewer.py
stays untouched.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

import yaml
from langchain_core.language_models import BaseChatModel

from mia.interviewer import (
    DEFAULT_LIMITS,
    InterviewLimits,
    InterviewState,
    TimeStatus,
    should_follow_up,
)
from mia.llm import DEFAULT_RUNS_DIR, load_models_config
from mia.prompts import load_prompt, resolve_prompt_model
from mia.schemas import InterviewPlan, Question, ToolMomentItem, Turn

DEFAULT_EXPERIMENT: Final = "baseline_v1_set_b"
QUESTIONS_PATH: Final = Path(__file__).resolve().parents[1] / "datasets" / "questions.yaml"
_INTERVIEWER: Final = "Entrevistador:"
_CANDIDATE: Final = "Candidato:"
_PLAN_MIN_QUESTIONS: Final = 4  # InterviewPlan requires at least 4 questions


def load_questions(path: Path = QUESTIONS_PATH) -> dict[str, Question]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {q["id"]: Question.model_validate(q) for q in data["questions"]}


def _turns_from_history(history: str, question_id: str, now: datetime) -> list[Turn]:
    """Rebuild Turns from "Entrevistador: ...\nCandidato: ..." text (inverse of _history_text)."""
    turns: list[Turn] = []
    target: str | None = None  # "interviewer" or "answer": where continuation lines go
    for line in history.splitlines():
        if line.startswith(_INTERVIEWER):
            turns.append(
                Turn(
                    session_id="eval",
                    turn_no=len(turns) + 1,
                    question_id=question_id,
                    interviewer_text=line.removeprefix(_INTERVIEWER).removeprefix(" "),
                    created_at=now,
                )
            )
            target = "interviewer"
        elif line.startswith(_CANDIDATE) and turns:
            turns[-1].answer_text = line.removeprefix(_CANDIDATE).removeprefix(" ")
            target = "answer"
        elif turns and target == "answer":
            turns[-1].answer_text = f"{turns[-1].answer_text}\n{line}"
        elif turns:
            turns[-1].interviewer_text = f"{turns[-1].interviewer_text}\n{line}"
    return turns


def build_state(
    item: ToolMomentItem, question: Question, limits: InterviewLimits = DEFAULT_LIMITS
) -> InterviewState:
    """Minimal InterviewState with only what should_follow_up reads (history, follow-ups used)."""
    now = datetime.now(UTC)
    plan = InterviewPlan(
        persona="technical",
        language="pt-BR",
        estimated_minutes=15,
        questions=[question] * _PLAN_MIN_QUESTIONS,
    )
    turns = _turns_from_history(item.history, question.id, now)
    return InterviewState(
        session_id="eval",
        plan=plan,
        current_index=0,
        follow_ups_used=limits.max_follow_ups - item.follow_ups_left,
        turn_count=len(turns),
        started_at=now,
        turns=turns,
    )


def _model_used(model: str | None) -> str:
    """The model ref the prompt will run on: explicit config > prompt_models.follow_up."""
    spec = resolve_prompt_model(load_prompt("follow_up", 1), load_models_config(), model)
    return spec.ref


def run_tool_item(
    item: ToolMomentItem,
    question: Question,
    *,
    model: str | None,
    experiment: str,
    runs_dir: Path = DEFAULT_RUNS_DIR,
    chat_model: BaseChatModel | None = None,
) -> dict[str, Any]:
    """Decide on one moment. Errors become {"error": ...} so only this case fails."""
    try:
        state = build_state(item, question)
        status = TimeStatus(over=item.minutes_left <= 0, minutes_left=item.minutes_left)
        decision = should_follow_up(
            question,
            item.answer,
            state,
            status,
            model=model,
            experiment=experiment,
            runs_dir=runs_dir,
            chat_model=chat_model,
        )
        used = _model_used(model)
    except Exception as exc:  # noqa: BLE001 - one bad item must not stop the whole eval
        return {"error": f"{type(exc).__name__}: {exc}"}
    return {
        "output": decision.model_dump_json(),
        "metadata": {
            "item_id": item.item_id,
            "split": item.split,
            "expected_action": item.expected.action,
            "raw_action": decision.action,
            "model": used,
        },
    }


def _item_from_vars(context: dict[str, Any]) -> ToolMomentItem:
    raw = context["vars"]["item"]
    if isinstance(raw, str):
        return ToolMomentItem.model_validate_json(raw)
    return ToolMomentItem.model_validate(raw)


def call_api(prompt: str, options: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Promptfoo entry point. ``prompt`` is only a marker; the real prompt is prompts/follow_up."""
    config = options.get("config") or {}
    try:
        item = _item_from_vars(context)
        question = load_questions()[item.question_id]
    except (KeyError, ValueError) as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
    return run_tool_item(
        item,
        question,
        model=config.get("model"),
        experiment=config.get("experiment", DEFAULT_EXPERIMENT),
    )
