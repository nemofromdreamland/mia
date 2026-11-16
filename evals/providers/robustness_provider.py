"""Promptfoo Python provider for set D (robustness, with and without a Bedrock Guardrail).

Thin on purpose: every attack goes through the real code (mia.judge, mia.interviewer,
mia.report_graph, mia.prep_graph), never a copy of a prompt. The guardrail, when on, travels in
``params={"guardrail": {...}}`` (spec 2.8a). Output of ``run_robustness_item``:
{"score", "summary_text", "prep_text", "interviewer_text", "blocked", "blocked_at"},
or {"error": ...} so a bad item fails alone.
"""

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

import yaml
from langchain_core.language_models import BaseChatModel

from mia.cases import CASES_DIR, load_case, load_case_texts
from mia.interviewer import (
    DEFAULT_LIMITS,
    InterviewState,
    TimeStatus,
    should_follow_up,
)
from mia.judge import default_scorer, judge_answer
from mia.llm import DEFAULT_RUNS_DIR, GuardrailBlocked
from mia.pii import mask_text
from mia.prep_graph import PrepInput, PrepValidationError, run_prep
from mia.report_graph import build_report_graph
from mia.schemas import (
    AnswerScore,
    InterviewPlan,
    Question,
    RobustnessItem,
    Turn,
)

DEFAULT_EXPERIMENT: Final = "robustness_v1"
ROOT: Final = Path(__file__).resolve().parents[2]
QUESTIONS_PATH: Final = ROOT / "evals" / "datasets" / "questions.yaml"
GUARDRAILS_PATH: Final = ROOT / "config" / "guardrails.yaml"
_PLAN_MIN_QUESTIONS: Final = 4  # InterviewPlan requires at least 4 questions
_MINUTES_LEFT: Final = 10.0
_SESSION: Final = "eval"


def load_questions(path: Path = QUESTIONS_PATH) -> dict[str, Question]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {q["id"]: Question.model_validate(q) for q in data["questions"]}


def load_guardrail(name: str, path: Path = GUARDRAILS_PATH) -> dict[str, str]:
    """{"id", "version"} of a guardrail named in config/guardrails.yaml."""
    entry = yaml.safe_load(path.read_text(encoding="utf-8"))[name]
    return {"id": str(entry["id"]), "version": str(entry["version"])}


def apply_injection(
    item: RobustnessItem, cases_dir: Path = CASES_DIR, out_dir: Path | None = None
) -> PrepInput:
    """Append ``injected_text`` to the CV or the job of the base case.

    PrepInput takes the CV as a file, so the (possibly injected) CV is written to ``out_dir``
    (a fresh temp folder by default); the job text travels in the object.
    """
    assert item.base_case_id is not None and item.injected_text is not None
    cv_text, job_text = load_case_texts(item.base_case_id, cases_dir)
    if item.target == "cv":
        cv_text = f"{cv_text}\n\n{item.injected_text}"
    else:
        job_text = f"{job_text}\n\n{item.injected_text}"
    folder = out_dir if out_dir is not None else Path(tempfile.mkdtemp(prefix="mia-rob-"))
    cv_path = folder / f"{item.item_id}-cv.md"
    cv_path.write_text(cv_text, encoding="utf-8")
    case = load_case(item.base_case_id, cases_dir).case
    return PrepInput(
        cv_path=cv_path,
        job_text=job_text,
        persona=case.persona,
        level=case.level,
        estimated_minutes=case.estimated_minutes,
        language=case.language,
    )


def _plan(question: Question) -> InterviewPlan:
    return InterviewPlan(
        persona="technical",
        language="pt-BR",
        estimated_minutes=15,
        questions=[question] * _PLAN_MIN_QUESTIONS,
    )


def _turn(question: Question, answer: str, interviewer_text: str = "") -> Turn:
    return Turn(
        session_id=_SESSION,
        turn_no=1,
        question_id=question.id,
        interviewer_text=interviewer_text or question.text,
        answer_text=answer,
        created_at=datetime.now(UTC),
    )


def _prep_text(screening: Any, plan: Any) -> str:
    return f"{screening.model_dump_json()}\n{plan.model_dump_json()}"


def _run_prep_item(item: RobustnessItem, options: dict[str, Any]) -> dict[str, Any]:
    data = apply_injection(item)
    try:
        result = run_prep(data, params=options["params"], **options["llm"])
        screening, plan = result.screening, result.plan
    except PrepValidationError as exc:  # invalid but generated: the text still counts (R5)
        screening, plan = exc.screening, exc.plan
    return {"prep_text": _prep_text(screening, plan)}


def _summary_text(
    question: Question, answer: str, score: AnswerScore, options: dict[str, Any]
) -> str:
    turn = _turn(question, answer).model_copy(update={"score": score})
    graph = build_report_graph(
        scorer=default_scorer(params=options["params"], **options["llm"]),
        params=options["params"],
        **options["llm"],
    )
    state = graph.invoke({"plan": _plan(question), "turns": [turn]})
    return state["summary"].model_dump_json()


def _interviewer_text(question: Question, answer: str, options: dict[str, Any]) -> str:
    now = datetime.now(UTC)
    state = InterviewState(
        session_id=_SESSION,
        plan=_plan(question),
        current_index=0,
        follow_ups_used=0,
        turn_count=1,
        started_at=now,
        turns=[_turn(question, answer)],
    )
    status = TimeStatus(over=False, minutes_left=_MINUTES_LEFT)
    decision = should_follow_up(
        question, answer, state, status, limits=DEFAULT_LIMITS, params=options["params"],
        **options["llm"],
    )  # fmt: skip
    return decision.follow_up_text or ""


def _run_answer_item(
    item: RobustnessItem, options: dict[str, Any], stage: list[str]
) -> dict[str, Any]:
    assert item.question_id is not None and item.answer_text is not None
    question = load_questions()[item.question_id]
    masked = mask_text(item.answer_text)
    out: dict[str, Any] = {}
    stage[0] = "judge"
    score = judge_answer(question, masked, params=options["params"], **options["llm"])
    out["score"] = score.score
    if item.expected.forbidden_in_summary:
        stage[0] = "summary"
        out["summary_text"] = _summary_text(question, masked, score, options)
    if item.attack_type == "off_topic":
        stage[0] = "interviewer"
        out["interviewer_text"] = _interviewer_text(question, masked, options)
    return out


def run_robustness_item(
    item: RobustnessItem,
    *,
    model: str | None,
    guardrail: dict[str, str] | None,
    experiment: str,
    runs_dir: Path = DEFAULT_RUNS_DIR,
    chat_model: BaseChatModel | None = None,
) -> dict[str, Any]:
    """Run one attack through the real pipeline; errors become {"error": ...}."""
    options = {
        "params": {"guardrail": guardrail} if guardrail else None,
        "llm": {
            "model": model,
            "experiment": experiment,
            "runs_dir": runs_dir,
            "chat_model": chat_model,
        },
    }
    result: dict[str, Any] = {
        "score": None,
        "summary_text": "",
        "prep_text": "",
        "interviewer_text": "",
        "blocked": False,
        "blocked_at": None,
    }
    stage = ["prep"]
    try:
        if item.attack_type == "doc_injection":
            result |= _run_prep_item(item, options)
        else:
            result |= _run_answer_item(item, options, stage)
    except GuardrailBlocked:
        result |= {"blocked": True, "blocked_at": stage[0]}
    except Exception as exc:  # noqa: BLE001 - one bad item must not stop the whole eval
        return {"error": f"{type(exc).__name__}: {exc}"}
    return result


def _item_from_vars(context: dict[str, Any]) -> RobustnessItem:
    raw = context["vars"]["item"]
    if isinstance(raw, str):
        return RobustnessItem.model_validate_json(raw)
    return RobustnessItem.model_validate(raw)


def call_api(prompt: str, options: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Promptfoo entry point. ``prompt`` is only a marker; config.guardrail names the guardrail."""
    config = options.get("config") or {}
    try:
        item = _item_from_vars(context)
        name = config.get("guardrail")
        guardrail = load_guardrail(name) if name else None
    except (KeyError, ValueError, OSError) as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
    output = run_robustness_item(
        item,
        model=config.get("model"),
        guardrail=guardrail,
        experiment=config.get("experiment", DEFAULT_EXPERIMENT),
    )
    if "error" in output:
        return output
    return {
        "output": json.dumps(output, ensure_ascii=False),
        "metadata": {
            "item_id": item.item_id,
            "attack_type": item.attack_type,
            "split": item.split,
            "max_score": item.expected.max_score,
            "guardrail": bool(guardrail),
        },
    }
