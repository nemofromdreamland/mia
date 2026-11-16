"""R6 (2.8a): `params` reaches the LLM layer from judge, prep, report and interviewer."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from mia import interviewer, judge, prep_graph, report_graph
from mia.interviewer import InterviewState, TimeStatus
from mia.prompts import PromptSpec, load_prompt, run_prompt_structured
from mia.schemas import AnswerScore, Question

GUARD = {"guardrail": {"id": "abc", "version": "1"}}
QUESTION = Question(
    id="q1",
    phase="projects",
    competency="Python",
    text="Conte um projeto.",
    purpose="Checar profundidade.",
    look_for=["cita exemplo", "mede resultado", "explica trade-off"],
    follow_ups=[],
)


class Recorder:
    """Stands in for run_prompt_structured and remembers the kwargs it received."""

    def __init__(self, result: Any) -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    def __call__(self, prompt: PromptSpec, variables: Any, schema: Any, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.result


def _score() -> AnswerScore:
    return AnswerScore(score=3, criteria_met=[], evidence_quotes=[], justification="ok")


def test_judge_answer_forwards_params(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = Recorder(_score())
    monkeypatch.setattr(judge, "run_prompt_structured", recorder)
    judge.judge_answer(QUESTION, "resposta", params=GUARD)
    assert recorder.calls[0]["params"] == GUARD


def test_judge_answer_default_params_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = Recorder(_score())
    monkeypatch.setattr(judge, "run_prompt_structured", recorder)
    judge.judge_answer(QUESTION, "resposta")
    assert recorder.calls[0]["params"] is None


def test_should_follow_up_forwards_params(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = Recorder("decision")
    monkeypatch.setattr(interviewer, "run_prompt_structured", recorder)
    state = InterviewState.model_construct(session_id="s-1", follow_ups_used=0, turns=[])
    status = TimeStatus(over=False, minutes_left=10.0)
    interviewer.should_follow_up(QUESTION, "resp", state, status, params=GUARD)
    assert recorder.calls[0]["params"] == GUARD


def test_report_graph_forwards_params_to_both_prompts(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[dict[str, Any] | None] = []

    def fake(prompt: PromptSpec, variables: Any, schema: Any, **kwargs: Any) -> Any:
        captured.append(kwargs.get("params"))
        raise RuntimeError("stop")

    monkeypatch.setattr(report_graph, "run_prompt_structured", fake)
    monkeypatch.setattr(report_graph, "ensure_scores", lambda plan, turns, scorer: turns)
    monkeypatch.setattr(
        report_graph, "aggregate_scores", lambda plan, turns: ({"Python": 3.0}, 3.0)
    )
    graph = report_graph.build_report_graph(scorer=lambda q, a: _score(), params=GUARD)
    with pytest.raises(RuntimeError):
        graph.invoke({"plan": SimpleNamespace(questions=[]), "turns": []})
    assert captured == [GUARD]


def test_prep_graph_accepts_params() -> None:
    graph = prep_graph.build_prep_graph(params=GUARD)
    assert graph is not None


def test_run_prompt_structured_merges_params_over_prompt_params(tmp_path: Path) -> None:
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
    from langchain_core.messages import AIMessage

    reply = '{"score": 3, "criteria_met": [], "evidence_quotes": [], "justification": "ok"}'
    fake = GenericFakeChatModel(messages=iter([AIMessage(content=reply)]))
    run_prompt_structured(
        load_prompt("judge", 1),
        {"question": "q", "look_for": "l", "answer": "a"},
        AnswerScore,
        chat_model=fake,
        runs_dir=tmp_path,
        params={"x": 1},
    )
    record = next(tmp_path.glob("*.jsonl")).read_text(encoding="utf-8")
    assert '"x":1' in record
