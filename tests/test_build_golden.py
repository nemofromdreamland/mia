"""Tests for scripts/build_golden.py (task 2.2, step 2). Fake chat model, no real calls."""

import importlib.util
import json
from collections.abc import Iterator
from itertools import cycle
from pathlib import Path
from types import ModuleType

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from mia.schemas import GoldenItem, Question


def _load_script() -> ModuleType:
    path = Path(__file__).parents[1] / "scripts" / "build_golden.py"
    spec = importlib.util.spec_from_file_location("build_golden", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bg = _load_script()

CASE_ID = "prompt-engineer-jr"
GENERATED_BY = "groq:openai/gpt-oss-120b|synthetic_candidate@v4"


class SpyModel(GenericFakeChatModel):
    """Fake model that returns fixed text and records every prompt it receives."""

    seen: list[str] = []

    def _generate(self, messages, *args, **kwargs):  # type: ignore[no-untyped-def]
        self.seen.append("\n".join(str(m.content) for m in messages))
        return super()._generate(messages, *args, **kwargs)


def _fake(text: str = "Resposta fixa.") -> SpyModel:
    messages: Iterator[AIMessage] = cycle([AIMessage(content=text)])
    return SpyModel(messages=messages, seen=[])


def _question(qid: str) -> Question:
    return Question(
        id=qid,
        phase="technical",
        competency="Avaliação de prompts",
        text="Como você compararia duas versões de um prompt?",
        purpose="Verificar avaliação sistemática.",
        look_for=["a", "b", "c"],
        follow_ups=[],
    )


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A temporary cases dir with one case; both test questions map to it."""
    folder = tmp_path / "cases" / CASE_ID
    folder.mkdir(parents=True)
    (folder / "case.yaml").write_text("case_id: x\n", encoding="utf-8")
    (folder / "cv.md").write_text(
        "Ana Fictícia\nana@exemplo.com\nTrabalhei com prompts.", encoding="utf-8"
    )
    (folder / "job.md").write_text("Vaga fictícia.", encoding="utf-8")
    monkeypatch.setitem(bg.QUESTION_CASE, "q-1", CASE_ID)
    monkeypatch.setitem(bg.QUESTION_CASE, "q-2", CASE_ID)
    return tmp_path / "cases"


def _build(env: Path, runs: Path, model: SpyModel) -> list[GoldenItem]:
    questions = [_question("q-1"), _question("q-2")]
    return bg.build_items(questions, chat_model=model, cases_dir=env, runs_dir=runs)


def test_happy_path_seven_variants_per_question(env: Path, tmp_path: Path) -> None:
    items = _build(env, tmp_path / "runs", _fake())
    assert len(items) == 14
    ids = [i.item_id for i in items]
    assert len(set(ids)) == 14
    assert ids[:7] == [f"q-1-{v}" for v in bg.VARIANTS]
    assert {i.variant for i in items} == set(bg.VARIANTS)


def test_paraphrase_points_to_level_3_and_others_are_null(env: Path, tmp_path: Path) -> None:
    items = _build(env, tmp_path / "runs", _fake())
    by_id = {i.item_id: i for i in items}
    assert by_id["q-1-paraphrase"].paraphrase_of == "q-1-level_3"
    assert by_id["q-2-paraphrase"].paraphrase_of == "q-2-level_3"
    others = [i for i in items if i.variant != "paraphrase"]
    assert all(i.paraphrase_of is None for i in others)


def test_paraphrase_prompt_receives_the_level_3_answer(env: Path, tmp_path: Path) -> None:
    model = _fake("Texto do nível três.")
    _build(env, tmp_path / "runs", model)
    assert "<resposta_base>Texto do nível três.</resposta_base>" in model.seen[6]
    assert "<resposta_base></resposta_base>" in model.seen[0]


def test_generated_by_names_model_and_prompt_version(env: Path, tmp_path: Path) -> None:
    items = _build(env, tmp_path / "runs", _fake())
    assert {i.generated_by for i in items} == {GENERATED_BY}
    assert all(i.human_score is None and i.split is None for i in items)


def test_cv_is_masked_before_the_model(env: Path, tmp_path: Path) -> None:
    model = _fake()
    _build(env, tmp_path / "runs", model)
    sent = "\n".join(model.seen)
    assert "ana@exemplo.com" not in sent
    assert "Fictícia" not in sent
    assert "[EMAIL]" in sent


def test_run_records_use_golden_experiment(env: Path, tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    _build(env, runs, _fake())
    (file,) = runs.glob("*_golden-2.2.jsonl")
    records = [json.loads(line) for line in file.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 14
    assert {r["experiment"] for r in records} == {"golden-2.2"}
    assert {r["prompt_version"] for r in records} == {4}


def test_blank_answer_fails_naming_the_item(env: Path, tmp_path: Path) -> None:
    with pytest.raises(bg.GoldenBuildError, match="q-1-level_5"):
        _build(env, tmp_path / "runs", _fake("   "))


def test_main_writes_nothing_when_an_answer_is_blank(
    env: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    questions = tmp_path / "questions.yaml"
    questions.write_text(
        "questions:\n  - id: q-1\n    phase: technical\n    competency: c\n    text: t\n"
        "    purpose: p\n    look_for: [a, b, c]\n    follow_ups: []\n",
        encoding="utf-8",
    )
    out = tmp_path / "out.jsonl"
    monkeypatch.setattr(bg, "QUESTIONS_PATH", questions)
    monkeypatch.setattr(bg, "OUTPUT_PATH", out)
    monkeypatch.setattr(bg, "CASES_DIR", env)
    monkeypatch.setattr(bg, "DEFAULT_RUNS_DIR", tmp_path / "runs")
    assert bg.main([], chat_model=_fake("  ")) == 1
    assert "q-1-level_5" in capsys.readouterr().err
    assert not out.exists()


def test_question_without_case_fails_clearly(env: Path, tmp_path: Path) -> None:
    with pytest.raises(bg.GoldenBuildError, match="q-unknown"):
        bg.build_items(
            [_question("q-unknown")],
            chat_model=_fake(),
            cases_dir=env,
            runs_dir=tmp_path / "runs",
        )


def test_refuses_to_overwrite_without_force(env: Path, tmp_path: Path) -> None:
    items = _build(env, tmp_path / "runs", _fake())
    out = tmp_path / "out.jsonl"
    out.write_text("human notes", encoding="utf-8")
    with pytest.raises(bg.GoldenBuildError, match="--force"):
        bg.write_jsonl(items, out, force=False)
    assert out.read_text(encoding="utf-8") == "human notes"
    bg.write_jsonl(items, out, force=True)
    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 14
    assert GoldenItem.model_validate_json(lines[0]).item_id == "q-1-level_5"


def test_main_refuses_existing_output_and_returns_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    out = tmp_path / "out.jsonl"
    out.write_text("keep", encoding="utf-8")
    monkeypatch.setattr(bg, "OUTPUT_PATH", out)
    assert bg.main([], chat_model=_fake()) == 1
    assert "--force" in capsys.readouterr().err
    assert out.read_text(encoding="utf-8") == "keep"


def test_question_case_covers_the_ten_real_questions() -> None:
    questions = bg.load_questions()
    assert len(questions) == 10
    assert {q.id for q in questions} == set(bg.QUESTION_CASE)
