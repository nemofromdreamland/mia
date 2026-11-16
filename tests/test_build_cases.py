"""Tests for scripts/build_cases.py (task 1.12, step 2). Fake prep, temporary cases dir."""

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest
import yaml

from mia.cases import load_case
from mia.llm import ModelConfigError
from mia.prep_graph import PrepInput, PrepResult, PrepValidationError
from mia.schemas import InterviewPlan, Screening


def _load_script() -> ModuleType:
    path = Path(__file__).parents[1] / "scripts" / "build_cases.py"
    spec = importlib.util.spec_from_file_location("build_cases", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build_cases = _load_script()

PREP_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "prep"


def _result() -> PrepResult:
    read = lambda name: (PREP_FIXTURES / name).read_text(encoding="utf-8")  # noqa: E731
    return PrepResult(
        screening=Screening.model_validate_json(read("screening_ok.json")),
        plan=InterviewPlan.model_validate_json(read("plan_ok.json")),
    )


def _make_case(root: Path, case_id: str) -> Path:
    folder = root / case_id
    folder.mkdir(parents=True)
    meta = {
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
    (folder / "case.yaml").write_text(yaml.safe_dump(meta), encoding="utf-8")
    (folder / "cv.md").write_text("Ana Fictícia\nCV fictício.", encoding="utf-8")
    (folder / "job.md").write_text("Vaga fictícia.", encoding="utf-8")
    return folder


def test_build_one_case_writes_loadable_fixtures(tmp_path: Path, capsys) -> None:
    _make_case(tmp_path, "prompt-engineer-jr")
    code = build_cases.main(
        ["--case", "prompt-engineer-jr"], prep=lambda data: _result(), cases_dir=tmp_path
    )
    assert code == 0
    assert (tmp_path / "prompt-engineer-jr" / "screening.json").is_file()
    assert load_case("prompt-engineer-jr", tmp_path).plan.questions
    assert "version" in capsys.readouterr().out


def test_without_args_builds_every_case(tmp_path: Path) -> None:
    _make_case(tmp_path, "a-case")
    _make_case(tmp_path, "b-case")
    assert build_cases.main([], prep=lambda data: _result(), cases_dir=tmp_path) == 0
    assert (tmp_path / "a-case" / "plan.json").is_file()
    assert (tmp_path / "b-case" / "plan.json").is_file()


def test_failure_writes_nothing_for_that_case_and_continues(tmp_path: Path, capsys) -> None:
    _make_case(tmp_path, "a-case")
    _make_case(tmp_path, "b-case")

    def prep(data: PrepInput) -> PrepResult:
        if data.cv_path.parent.name == "a-case":
            raise PrepValidationError(["falta pergunta"])
        return _result()

    assert build_cases.main([], prep=prep, cases_dir=tmp_path) == 1
    assert not (tmp_path / "a-case" / "screening.json").exists()
    assert not (tmp_path / "a-case" / "plan.json").exists()
    assert (tmp_path / "b-case" / "plan.json").is_file()
    assert "a-case" in capsys.readouterr().err


def test_model_config_error_exits_2(tmp_path: Path) -> None:
    _make_case(tmp_path, "a-case")

    def prep(data: PrepInput) -> PrepResult:
        raise ModelConfigError("sem chave")

    assert build_cases.main([], prep=prep, cases_dir=tmp_path) == 2


def test_unknown_case_exits_1(tmp_path: Path, capsys) -> None:
    _make_case(tmp_path, "a-case")
    code = build_cases.main(["--case", "nao-existe"], prep=lambda d: _result(), cases_dir=tmp_path)
    assert code == 1
    assert "nao-existe" in capsys.readouterr().err


def test_prep_input_comes_from_case_files(tmp_path: Path) -> None:
    _make_case(tmp_path, "a-case")
    seen: list[PrepInput] = []

    def prep(data: PrepInput) -> PrepResult:
        seen.append(data)
        return _result()

    build_cases.main([], prep=prep, cases_dir=tmp_path)
    data = seen[0]
    assert data.cv_path.name == "cv.md"
    assert data.job_text == "Vaga fictícia."
    assert (data.persona, data.level, data.estimated_minutes) == ("technical", "junior", 10)
    assert data.language == "pt-BR"


def test_fixtures_are_utf8_indented(tmp_path: Path) -> None:
    _make_case(tmp_path, "a-case")
    build_cases.main([], prep=lambda d: _result(), cases_dir=tmp_path)
    text = (tmp_path / "a-case" / "plan.json").read_text(encoding="utf-8")
    assert text.startswith('{\n  "')
    json.loads(text)


@pytest.mark.parametrize("flag", ["--bogus"])
def test_bad_flag_exits_2(flag: str) -> None:
    with pytest.raises(SystemExit) as exc:
        build_cases.main([flag], prep=lambda d: _result())
    assert exc.value.code == 2
