"""Tests for the case loader (task 1.12, step 1). Uses a temporary cases dir."""

import json
from pathlib import Path

import pytest
import yaml

from mia.cases import (
    CaseError,
    CaseNotFoundError,
    LoadedCase,
    list_cases,
    load_case,
    load_case_texts,
    write_fixtures,
)
from mia.prep_graph import PrepResult
from mia.schemas import InterviewPlan, Screening

PREP_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "prep"
CASE_ID = "prompt-engineer-jr"


def _case_yaml(case_id: str = CASE_ID) -> dict[str, object]:
    return {
        "case_id": case_id,
        "title": "Engenheiro(a) de Prompt Jr",
        "company": "Nexa Consultoria",
        "level": "junior",
        "persona": "technical",
        "language": "pt-BR",
        "blurb": "Vaga fictícia.",
        "candidate_blurb": "Você é Ana.",
        "estimated_minutes": 10,
        "version": 1,
    }


def _screening_raw() -> dict[str, object]:
    return json.loads((PREP_FIXTURES / "screening_ok.json").read_text(encoding="utf-8"))


def _plan_raw() -> dict[str, object]:
    return json.loads((PREP_FIXTURES / "plan_ok.json").read_text(encoding="utf-8"))


def _make_case(
    root: Path,
    folder: str = CASE_ID,
    *,
    meta: dict[str, object] | None = None,
    screening: dict[str, object] | None = None,
    plan: dict[str, object] | None = None,
    with_screening: bool = True,
    with_plan: bool = True,
) -> Path:
    case_dir = root / folder
    case_dir.mkdir(parents=True)
    meta = meta if meta is not None else _case_yaml(folder)
    (case_dir / "case.yaml").write_text(yaml.safe_dump(meta), encoding="utf-8")
    (case_dir / "cv.md").write_text("Ana Fictícia\nCV fictício.", encoding="utf-8")
    (case_dir / "job.md").write_text("Vaga fictícia.", encoding="utf-8")
    if with_screening:
        data = screening if screening is not None else _screening_raw()
        (case_dir / "screening.json").write_text(json.dumps(data), encoding="utf-8")
    if with_plan:
        data = plan if plan is not None else _plan_raw()
        (case_dir / "plan.json").write_text(json.dumps(data), encoding="utf-8")
    return case_dir


def test_load_case_returns_validated_objects(tmp_path: Path) -> None:
    _make_case(tmp_path)
    loaded = load_case(CASE_ID, tmp_path)
    assert isinstance(loaded, LoadedCase)
    assert loaded.case.case_id == CASE_ID
    assert isinstance(loaded.screening, Screening)
    assert isinstance(loaded.plan, InterviewPlan)


@pytest.mark.parametrize("bad_id", ["../etc", "Prompt", "a/b", "", "-x", "x-", "a--b"])
def test_load_case_rejects_bad_id(tmp_path: Path, bad_id: str) -> None:
    with pytest.raises(CaseNotFoundError):
        load_case(bad_id, tmp_path)


def test_load_case_missing_folder(tmp_path: Path) -> None:
    with pytest.raises(CaseNotFoundError, match="nao-existe"):
        load_case("nao-existe", tmp_path)


@pytest.mark.parametrize(
    ("kwargs", "filename"),
    [({"with_plan": False}, "plan.json"), ({"with_screening": False}, "screening.json")],
)
def test_load_case_missing_fixture(tmp_path: Path, kwargs: dict[str, bool], filename: str) -> None:
    _make_case(tmp_path, **kwargs)
    with pytest.raises(CaseError, match=filename) as exc:
        load_case(CASE_ID, tmp_path)
    assert CASE_ID in str(exc.value)


def test_load_case_invalid_screening(tmp_path: Path) -> None:
    screening = _screening_raw() | {"fit_score": 200}
    _make_case(tmp_path, screening=screening)
    with pytest.raises(CaseError, match="screening.json"):
        load_case(CASE_ID, tmp_path)


def test_load_case_invalid_yaml(tmp_path: Path) -> None:
    meta = _case_yaml() | {"level": "senior"}
    _make_case(tmp_path, meta=meta)
    with pytest.raises(CaseError, match="case.yaml"):
        load_case(CASE_ID, tmp_path)


def test_load_case_id_mismatch(tmp_path: Path) -> None:
    _make_case(tmp_path, "a-b", meta=_case_yaml("x-y"))
    with pytest.raises(CaseError, match="x-y"):
        load_case("a-b", tmp_path)


def test_load_case_coverage_problem(tmp_path: Path) -> None:
    screening = _screening_raw()
    screening["competencies"] = [*screening["competencies"], "Competência sem pergunta"]  # type: ignore[misc]
    _make_case(tmp_path, screening=screening)
    with pytest.raises(CaseError, match="Competência sem pergunta"):
        load_case(CASE_ID, tmp_path)


def test_list_cases_sorted_and_skips_folders_without_yaml(tmp_path: Path) -> None:
    _make_case(tmp_path, "b-case")
    _make_case(tmp_path, "a-case", with_plan=False)
    (tmp_path / "sem-yaml").mkdir()
    assert [case.case_id for case in list_cases(tmp_path)] == ["a-case", "b-case"]


def test_list_cases_empty_when_dir_missing(tmp_path: Path) -> None:
    assert list_cases(tmp_path / "nada") == []


def test_load_case_texts(tmp_path: Path) -> None:
    _make_case(tmp_path)
    assert load_case_texts(CASE_ID, tmp_path) == ("Ana Fictícia\nCV fictício.", "Vaga fictícia.")


def test_load_case_texts_missing_case(tmp_path: Path) -> None:
    with pytest.raises(CaseNotFoundError):
        load_case_texts("nao-existe", tmp_path)


def test_write_fixtures_roundtrip(tmp_path: Path) -> None:
    _make_case(tmp_path, with_screening=False, with_plan=False)
    result = PrepResult(
        screening=Screening.model_validate(_screening_raw()),
        plan=InterviewPlan.model_validate(_plan_raw()),
    )
    write_fixtures(CASE_ID, result, tmp_path)
    text = (tmp_path / CASE_ID / "plan.json").read_text(encoding="utf-8")
    assert text.startswith("{\n  ")  # indent=2
    assert "\\u00" not in text  # ensure_ascii=False
    loaded = load_case(CASE_ID, tmp_path)
    assert loaded.screening == result.screening
    assert loaded.plan == result.plan
