"""Short interview and uncut interviewer lines (task 4.7c)."""

import pytest

from mia import interviewer
from mia.cases import load_case
from mia.prompts import load_prompt
from mia.schemas import InterviewPlan

CASES = [
    "ai-product-manager",
    "backend-python-jr",
    "data-analyst-pleno",
    "prompt-engineer-jr",
    "software-intern",
]


# ---------- R2: never show a cut line ----------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Ótimo. Agora me conte, com con", "Ótimo."),
        ("Entendi! E como você mediu? Depois, com con", "Entendi! E como você mediu?"),
        ("Olá tudo bem", "Olá tudo bem"),
        ("Pode começar?", "Pode começar?"),
        ("Certo… e então", "Certo…"),
        ("  Tudo certo.  ", "Tudo certo."),
    ],
)
def test_finish_at_sentence(text: str, expected: str) -> None:
    assert interviewer.finish_at_sentence(text) == expected


# ---------- R1: prompt v2 ----------


def test_interviewer_v2_is_short_and_on_bedrock() -> None:
    prompt = load_prompt("interviewer", 2)
    assert prompt.params["max_tokens"] == 250
    assert "3 frases" in prompt.system
    assert prompt.model.startswith("bedrock:")
    assert prompt.changelog


def test_interviewer_v3_acknowledges_the_last_answer() -> None:
    prompt = load_prompt("interviewer", 3)
    assert prompt.params == load_prompt("interviewer", 2).params
    assert "2 a 6 palavras" in prompt.system
    assert "Vamos manter o foco na entrevista." in prompt.system
    assert prompt.model.startswith("bedrock:") and prompt.changelog


def test_interviewer_v4_keeps_short_on_topic_answers_out_of_the_focus_line() -> None:
    prompt = load_prompt("interviewer", 4)
    assert "NÃO é fora do tema" in prompt.system
    assert prompt.params == load_prompt("interviewer", 3).params and prompt.changelog


def test_default_writer_uses_v4_and_finishes_sentences(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}

    def fake_run(prompt, variables, **kwargs):  # type: ignore[no-untyped-def]
        seen["version"] = prompt.version
        return "Boa resposta. Agora me conte, com con"

    monkeypatch.setattr(interviewer, "run_prompt", fake_run)
    write = interviewer.default_writer(persona="technical")
    assert write("opening", "Q?", "faça", []) == "Boa resposta."
    assert seen["version"] == 4


# ---------- R3, R4: shorter interview ----------


def test_web_limits() -> None:
    limits = interviewer.WEB_LIMITS
    assert (limits.max_follow_ups, limits.max_questions) == (1, 3)
    assert (limits.target_minutes, limits.hard_max_minutes) == (6, 8)


def plan_with(phases: list[str]) -> InterviewPlan:
    base = load_case("prompt-engineer-jr").plan
    template = base.questions[0]
    questions = [
        template.model_copy(update={"id": f"q{i + 1}", "phase": phase})
        for i, phase in enumerate(phases)
    ]
    return base.model_copy(update={"questions": questions, "estimated_minutes": 10})


def test_shorten_plan_picks_opening_technical_behavioral() -> None:
    plan = plan_with(["opening", "project", "technical", "technical", "behavioral", "closing"])
    short = interviewer.shorten_plan(plan)
    assert [q.id for q in short.questions] == ["q1", "q3", "q5"]
    assert short.estimated_minutes == 6


def test_shorten_plan_fills_a_missing_phase_in_order() -> None:
    plan = plan_with(["opening", "project", "technical", "closing"])
    assert [q.id for q in interviewer.shorten_plan(plan).questions] == ["q1", "q2", "q3"]


def test_short_plan_is_unchanged() -> None:
    plan = plan_with(["opening", "technical"])
    assert [q.id for q in interviewer.shorten_plan(plan).questions] == ["q1", "q2"]


@pytest.mark.parametrize("case_id", CASES)
def test_real_cases_shorten_to_three(case_id: str) -> None:
    loaded = load_case(case_id)
    short = interviewer.shorten_plan(loaded.plan)
    assert len({q.id for q in short.questions}) == 3
    assert loaded.case.estimated_minutes == 6 and loaded.case.version == 3


def test_cli_limits_unchanged() -> None:
    limits = interviewer.DEFAULT_LIMITS
    assert (limits.max_follow_ups, limits.hard_max_minutes) == (2, 15)


def test_service_uses_web_limits() -> None:
    import inspect

    from mia import service

    source = inspect.getsource(service)
    assert source.count("limits=WEB_LIMITS") >= 2
    assert "shorten_plan(load_case(" in source
