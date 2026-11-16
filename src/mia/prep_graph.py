"""Preparation graph: CV file -> text -> masked -> screening -> plan -> coverage checks.

Used offline (case fixtures) and by the CLI; the web never uploads CVs.
"""

from pathlib import Path
from typing import Any, TypedDict

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from mia.checks import unverified_quotes
from mia.llm import DEFAULT_RUNS_DIR
from mia.pii import mask_cv, mask_text
from mia.prompts import load_prompt, run_prompt_structured
from mia.schemas import InterviewPlan, Language, Level, Persona, Screening

_TEXT_SUFFIXES = {".md", ".txt"}


class PrepError(Exception):
    """Preparation could not start or finish (bad input file, failed checks)."""


class PrepValidationError(PrepError):
    """Screening or plan failed the deterministic checks; keeps what the models returned."""

    def __init__(
        self,
        problems: list[str],
        screening: Screening | None = None,
        plan: InterviewPlan | None = None,
    ) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems
        self.screening = screening
        self.plan = plan


class PrepInput(BaseModel):
    cv_path: Path
    job_text: str
    persona: Persona
    level: Level
    estimated_minutes: int = Field(ge=5, le=45)
    language: Language = "pt-BR"


class PrepResult(BaseModel):
    screening: Screening
    plan: InterviewPlan


class PrepState(TypedDict, total=False):
    input: PrepInput
    cv_text: str
    cv_masked: str
    job_masked: str
    screening: Screening
    plan: InterviewPlan
    problems: list[str]


def _read_pdf(path: Path) -> str:
    try:
        reader = PdfReader(path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except (PdfReadError, OSError, ValueError) as exc:
        raise PrepError(f"{path}: não foi possível ler o PDF ({exc})") from exc


def extract_cv_text(path: Path) -> str:
    """Return the CV text from a .pdf, .md or .txt file; raise PrepError otherwise."""
    suffix = path.suffix.lower()
    if suffix != ".pdf" and suffix not in _TEXT_SUFFIXES:
        raise PrepError(f"{path}: formato não suportado (use .pdf, .md ou .txt)")
    if not path.is_file():
        raise PrepError(f"{path}: arquivo não encontrado")
    text = _read_pdf(path) if suffix == ".pdf" else path.read_text(encoding="utf-8")
    if not text.strip():
        raise PrepError(f"{path}: o CV não tem texto")
    return text


def check_screening_quotes(screening: Screening, cv_masked: str) -> list[str]:
    """Problems for every strength/concern quote not found literally in the masked CV."""
    evidence = [*screening.strengths, *screening.concerns]
    missing = unverified_quotes([item.cv_quote for item in evidence], cv_masked)
    return [f"citação não encontrada no CV: {quote!r}" for quote in missing]


def check_plan_coverage(screening: Screening, plan: InterviewPlan, persona: Persona) -> list[str]:
    """Structural coverage rules (code, not LLM). Returns ALL problems found."""
    problems: list[str] = []
    covered = {question.competency for question in plan.questions}
    problems += [
        f"competência sem pergunta: {competency!r}"
        for competency in screening.competencies
        if competency not in covered
    ]
    if not any(question.targets_concern for question in plan.questions):
        problems.append("nenhuma pergunta tem targets_concern (lacuna não explorada)")
    if plan.persona != persona:
        problems.append(f"persona do plano ({plan.persona}) difere da pedida ({persona})")
    seen: set[str] = set()
    for question in plan.questions:
        if question.id in seen:
            problems.append(f"id de pergunta repetido: {question.id!r}")
        seen.add(question.id)
    return problems


def build_prep_graph(
    *,
    model: str | None = None,
    experiment: str | None = None,
    session_id: str | None = None,
    runs_dir: Path = DEFAULT_RUNS_DIR,
    chat_model: BaseChatModel | None = None,
    screening_version: int = 1,
    planner_version: int = 1,
) -> CompiledStateGraph:
    """Straight-line graph: extract -> mask -> screen -> plan -> validate."""
    screening_prompt = load_prompt("screening", screening_version)
    planner_prompt = load_prompt("planner", planner_version)
    call_options: dict[str, Any] = {
        "model": model,
        "experiment": experiment,
        "session_id": session_id,
        "runs_dir": runs_dir,
        "chat_model": chat_model,
    }

    def _extract(state: PrepState) -> PrepState:
        return {"cv_text": extract_cv_text(state["input"].cv_path)}

    def _mask(state: PrepState) -> PrepState:
        return {
            "cv_masked": mask_cv(state["cv_text"]),
            "job_masked": mask_text(state["input"].job_text),
        }

    def _screen(state: PrepState) -> PrepState:
        screening = run_prompt_structured(
            screening_prompt,
            {"job": state["job_masked"], "cv": state["cv_masked"]},
            Screening,
            **call_options,
        )
        return {"screening": screening}

    def _plan(state: PrepState) -> PrepState:
        data = state["input"]
        plan = run_prompt_structured(
            planner_prompt,
            {
                "persona": data.persona,
                "level": data.level,
                "estimated_minutes": str(data.estimated_minutes),
                "job": state["job_masked"],
                "screening": state["screening"].model_dump_json(indent=2),
            },
            InterviewPlan,
            **call_options,
        )
        return {"plan": plan}

    def _validate(state: PrepState) -> PrepState:
        problems = check_screening_quotes(state["screening"], state["cv_masked"])
        problems += check_plan_coverage(state["screening"], state["plan"], state["input"].persona)
        return {"problems": problems}

    steps = [
        ("extract", _extract),
        ("mask", _mask),
        ("screen", _screen),
        ("plan", _plan),
        ("validate", _validate),
    ]
    graph = StateGraph(PrepState)
    for name, node in steps:
        graph.add_node(name, node)
    names = [name for name, _ in steps]
    graph.add_edge(START, names[0])
    for current, following in zip(names, names[1:], strict=False):
        graph.add_edge(current, following)
    graph.add_edge(names[-1], END)
    return graph.compile()


def run_prep(data: PrepInput, **graph_options: Any) -> PrepResult:
    """Run the preparation; raise PrepValidationError if any check finds a problem."""
    state = build_prep_graph(**graph_options).invoke({"input": data})
    if state["problems"]:
        raise PrepValidationError(state["problems"], state["screening"], state["plan"])
    return PrepResult(screening=state["screening"], plan=state["plan"])
