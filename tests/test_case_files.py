"""Content checks for the 5 ready-made cases in cases/ (task 1.11).

Reads the files directly; the production loader (src/mia/cases.py) is task 1.12.
"""

from pathlib import Path

import pytest
import yaml

from mia.pii import mask_text
from mia.schemas import Case, Level, Persona

CASES_DIR = Path(__file__).resolve().parent.parent / "cases"

EXPECTED: dict[str, tuple[str, str, Level, Persona]] = {
    "prompt-engineer-jr": ("Engenheiro(a) de Prompt Jr", "Nexa Consultoria", "junior", "technical"),
    "data-analyst-pleno": ("Analista de Dados Pleno", "Lumo", "mid", "technical"),
    "backend-python-jr": ("Desenvolvedor(a) Backend Python Jr", "Cofre", "junior", "hr"),
    "ai-product-manager": ("Product Manager de Produtos de IA", "Atlas", "mid", "manager"),
    "software-intern": ("Estágio em Desenvolvimento de Software", "Trilha", "internship", "hr"),
}
CASE_IDS: tuple[str, ...] = tuple(EXPECTED)
TEXT_FILES: tuple[str, ...] = ("cv.md", "job.md")


def _load_case(case_id: str) -> Case:
    raw = (CASES_DIR / case_id / "case.yaml").read_text(encoding="utf-8")
    return Case.model_validate(yaml.safe_load(raw))


def _words(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").split())


def test_cases_dir_has_exactly_the_five_cases() -> None:
    folders = {p.name for p in CASES_DIR.iterdir() if p.is_dir()}
    assert folders == set(CASE_IDS)


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_case_yaml_is_valid_and_matches_table(case_id: str) -> None:
    case = _load_case(case_id)
    title, company, level, persona = EXPECTED[case_id]
    assert case.case_id == case_id
    assert (case.title, case.company, case.level, case.persona) == (title, company, level, persona)
    assert case.language == "pt-BR"
    assert case.estimated_minutes == 6  # spec 4.7c: short web interview
    assert case.version == 2


@pytest.mark.parametrize("case_id", CASE_IDS)
@pytest.mark.parametrize("name", TEXT_FILES)
def test_text_file_exists_with_250_to_400_words(case_id: str, name: str) -> None:
    path = CASES_DIR / case_id / name
    assert path.is_file()
    assert 250 <= _words(path) <= 400


@pytest.mark.parametrize("case_id", CASE_IDS)
@pytest.mark.parametrize("name", TEXT_FILES)
def test_text_file_has_no_personal_data(case_id: str, name: str) -> None:
    text = (CASES_DIR / case_id / name).read_text(encoding="utf-8")
    assert mask_text(text) == text
