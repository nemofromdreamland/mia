"""Load and validate the ready-made demo cases in cases/<case_id>/ (no model calls)."""

import json
import re
from pathlib import Path
from typing import Final

import yaml
from pydantic import BaseModel, ValidationError

from mia.prep_graph import PrepResult, check_plan_coverage
from mia.schemas import Case, CaseExamples, InterviewPlan, Screening

CASES_DIR: Final[Path] = Path(__file__).resolve().parent.parent.parent / "cases"
_CASE_ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class CaseError(Exception):
    """A case exists but its files are missing or inconsistent."""


class CaseNotFoundError(CaseError):
    """Invalid case_id or no such case folder."""


class LoadedCase(BaseModel):
    case: Case
    screening: Screening
    plan: InterviewPlan


def _case_dir(case_id: str, cases_dir: Path) -> Path:
    if not _CASE_ID.fullmatch(case_id):
        raise CaseNotFoundError(f"case_id inválido: {case_id!r}")
    folder = cases_dir / case_id
    if not (folder / "case.yaml").is_file():
        raise CaseNotFoundError(f"caso não encontrado: {case_id!r}")
    return folder


def _read(folder: Path, filename: str) -> str:
    path = folder / filename
    if not path.is_file():
        raise CaseError(f"{folder.name}: arquivo ausente: {filename}")
    return path.read_text(encoding="utf-8")


def _parse_case(folder: Path) -> Case:
    try:
        return Case.model_validate(yaml.safe_load(_read(folder, "case.yaml")))
    except (ValidationError, yaml.YAMLError) as exc:
        raise CaseError(f"{folder.name}: case.yaml inválido: {exc}") from exc


def _parse_json[T: BaseModel](folder: Path, filename: str, schema: type[T]) -> T:
    try:
        return schema.model_validate_json(_read(folder, filename))
    except ValidationError as exc:
        raise CaseError(f"{folder.name}: {filename} inválido: {exc}") from exc


def list_cases(cases_dir: Path = CASES_DIR) -> list[Case]:
    """Metadata of every folder that has a case.yaml, sorted by case_id."""
    if not cases_dir.is_dir():
        return []
    folders = sorted(p for p in cases_dir.iterdir() if (p / "case.yaml").is_file())
    return sorted((_parse_case(folder) for folder in folders), key=lambda c: c.case_id)


def load_case(case_id: str, cases_dir: Path = CASES_DIR) -> LoadedCase:
    """Case + screening + plan, validated by schema and coverage rules."""
    folder = _case_dir(case_id, cases_dir)
    case = _parse_case(folder)
    if case.case_id != case_id:
        raise CaseError(f"{case_id}: case.yaml diz case_id {case.case_id!r}")
    screening = _parse_json(folder, "screening.json", Screening)
    plan = _parse_json(folder, "plan.json", InterviewPlan)
    problems = check_plan_coverage(screening, plan, case.persona)
    if problems:
        raise CaseError(f"{case_id}: plano inconsistente: " + "; ".join(problems))
    return LoadedCase(case=case, screening=screening, plan=plan)


EXAMPLES_FILE = "examples.json"


def load_examples(case_id: str, cases_dir: Path = CASES_DIR) -> CaseExamples:
    """Pre-generated strong/weak answers (spec 5.6); no model is called at runtime."""
    folder = _case_dir(case_id, cases_dir)
    examples = _parse_json(folder, EXAMPLES_FILE, CaseExamples)
    if examples.case_id != case_id:
        raise CaseError(f"{case_id}: {EXAMPLES_FILE} diz case_id {examples.case_id!r}")
    return examples


def load_case_texts(case_id: str, cases_dir: Path = CASES_DIR) -> tuple[str, str]:
    """(cv_text, job_text) of a case; used by scripts/build_cases.py."""
    folder = _case_dir(case_id, cases_dir)
    return _read(folder, "cv.md"), _read(folder, "job.md")


def write_fixtures(case_id: str, result: PrepResult, cases_dir: Path = CASES_DIR) -> None:
    """Write screening.json and plan.json (UTF-8, indent=2, readable accents)."""
    folder = _case_dir(case_id, cases_dir)
    for filename, model in (("screening.json", result.screening), ("plan.json", result.plan)):
        text = json.dumps(model.model_dump(mode="json"), indent=2, ensure_ascii=False)
        (folder / filename).write_text(text + "\n", encoding="utf-8")
