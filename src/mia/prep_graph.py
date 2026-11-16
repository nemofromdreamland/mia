"""Preparation graph: CV file -> text -> masked -> screening -> plan -> coverage checks.

Used offline (case fixtures) and by the CLI; the web never uploads CVs.
"""

from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from mia.checks import unverified_quotes
from mia.schemas import InterviewPlan, Persona, Screening

_TEXT_SUFFIXES = {".md", ".txt"}


class PrepError(Exception):
    """Preparation could not start or finish (bad input file, failed checks)."""


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
