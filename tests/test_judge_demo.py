"""Regression tests for the real-model judge demo."""

import importlib.util
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

from pydantic import BaseModel, ValidationError


def _load_demo() -> ModuleType:
    path = Path(__file__).parents[1] / "scripts" / "judge_demo.py"
    spec = importlib.util.spec_from_file_location("judge_demo", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


judge_demo = _load_demo()


class _RequiredSetting(BaseModel):
    api_key: str


def _missing_api_key_error() -> ValidationError:
    try:
        _RequiredSetting.model_validate({})
    except ValidationError as exc:
        return exc
    raise AssertionError("Expected fixture validation to fail")


def test_main_reports_configuration_error_without_traceback(
    monkeypatch, capsys
) -> None:
    judge = Mock(side_effect=_missing_api_key_error())
    monkeypatch.setattr(judge_demo, "judge_answer", judge)

    result = judge_demo.main()

    captured = capsys.readouterr()
    assert result == 2
    assert "Falha na chamada ao modelo:" in captured.err
    assert "Traceback" not in captured.err
    assert captured.out == ""
