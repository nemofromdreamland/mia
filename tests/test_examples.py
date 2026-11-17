"""Spec 5.6: pre-generated strong/weak answer examples (fixtures, service, API, script)."""

import importlib.util
import json
from pathlib import Path

import pytest
from fakes_service import CASE_ID, VISITOR_A, VISITOR_B, make_deps
from fastapi.testclient import TestClient

from mia.api import create_app
from mia.cases import CASES_DIR, list_cases, load_case, load_examples
from mia.interviewer import shorten_plan
from mia.service import ServiceError, create_session, get_examples, start_interview

_spec = importlib.util.spec_from_file_location(
    "build_examples", Path(__file__).parent.parent / "scripts" / "build_examples.py"
)
assert _spec is not None and _spec.loader is not None
build_examples = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_examples)


@pytest.mark.parametrize("case_id", [c.case_id for c in list_cases()])
def test_every_short_plan_question_has_strong_and_weak(case_id: str) -> None:
    examples = load_examples(case_id)
    by_id = {e.question_id: e for e in examples.examples}
    for question in shorten_plan(load_case(case_id).plan).questions:
        example = by_id[question.id]
        assert example.strong.strip() and example.weak.strip()
        assert example.strong != example.weak
        assert len(example.strong.split()) <= 160 and len(example.weak.split()) <= 120


def started(deps, visitor: str = VISITOR_A) -> str:
    sid = create_session(deps, visitor, CASE_ID, "text").session_id
    start_interview(deps, visitor, sid)
    return sid


def test_get_examples_returns_current_question_and_marks_session() -> None:
    deps = make_deps()
    sid = started(deps)
    session = deps.repo.get_session(VISITOR_A, sid)
    assert session.examples_seen is False
    view = get_examples(deps, VISITOR_A, sid)
    assert view.question_id == session.current_question_id
    assert view.strong and view.weak
    assert deps.repo.get_session(VISITOR_A, sid).examples_seen is True
    get_examples(deps, VISITOR_A, sid)  # second time: no extra update, same answer


def test_get_examples_other_visitor_and_wrong_state() -> None:
    deps = make_deps()
    sid = started(deps)
    with pytest.raises(ServiceError) as other:
        get_examples(deps, VISITOR_B, sid)
    assert other.value.code == "not_found"
    ready = create_session(deps, VISITOR_A, CASE_ID, "text").session_id
    with pytest.raises(ServiceError) as wrong:
        get_examples(deps, VISITOR_A, ready)
    assert wrong.value.code == "invalid_state"


def test_examples_rest_and_invocations() -> None:
    deps = make_deps()
    sid = started(deps)
    client = TestClient(create_app(deps))
    rest = client.get(f"/sessions/{sid}/examples", headers={"X-Visitor-Id": VISITOR_A})
    assert rest.status_code == 200
    assert set(rest.json()) == {"question_id", "turn_no", "strong", "weak"}
    inv = client.post(
        "/invocations",
        json={"action": "get_examples", "visitor_id": VISITOR_A, "session_id": sid},
    )
    assert inv.json() == rest.json()


def test_build_examples_script_with_fake_generator(tmp_path) -> None:
    calls = []

    def fake(question, cv_masked, target):
        calls.append(target[0])
        return f"{target[0]}: {question.id}"

    examples = build_examples.build_case(CASE_ID, fake, CASES_DIR)
    assert {e.question_id for e in examples.examples} == {
        q.id for q in shorten_plan(load_case(CASE_ID).plan).questions
    }
    assert set(calls) == {"5", "2"}
    assert examples.generated_by.startswith("synthetic_candidate@v")
    (tmp_path / CASE_ID).mkdir()
    path = build_examples.write(examples, tmp_path)
    assert json.loads(path.read_text(encoding="utf-8"))["case_id"] == CASE_ID


def test_follow_up_gets_a_fresh_runtime_suggestion() -> None:
    from mia.schemas import AnswerExample, ToolDecision

    seen = []

    def suggest(case_id, question_id, text, key):
        seen.append((case_id, question_id, text, key))
        return AnswerExample(question_id=question_id, strong="forte nova", weak="fraca nova")

    deps = make_deps(scorer=lambda q, a: None).model_copy(
        update={
            "suggest": suggest,
            "decider": lambda q, a, s, t: ToolDecision(
                action="follow_up", follow_up_text="E o desafio?", reason="raso"
            ),
        }
    )
    sid = started(deps)
    plan_view = get_examples(deps, VISITOR_A, sid)
    from mia.service import send_answer

    send_answer(deps, VISITOR_A, sid, "Usei Python.")
    view = get_examples(deps, VISITOR_A, sid)
    last = deps.repo.list_turns(VISITOR_A, sid)[-1]
    assert last.is_follow_up
    assert (view.strong, view.weak) == ("forte nova", "fraca nova")
    assert view.turn_no == last.turn_no and view.turn_no != plan_view.turn_no
    assert seen == [(CASE_ID, last.question_id, last.interviewer_text, f"{sid}#{last.turn_no}")]


def test_model_suggest_caches_per_key(monkeypatch) -> None:
    from mia import suggestions

    calls = []
    monkeypatch.setattr(
        suggestions,
        "generate_answer",
        lambda text, cv, target, model=None: calls.append(model) or f"{target[0]} {text}",
    )
    suggest = suggestions.model_suggest()
    first = suggest(CASE_ID, "q1", "E o desafio?", "k")
    again = suggest(CASE_ID, "q1", "E o desafio?", "k")
    assert first is again and len(calls) == 2  # strong + weak, once
    assert set(calls) == {suggestions.RUNTIME_MODEL}
