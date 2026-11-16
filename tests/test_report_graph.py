"""Tests for the report graph: deterministic scoring, aggregation and checks."""

import json
from pathlib import Path

import pytest

from mia.report_graph import (
    ReportError,
    ReportValidationError,
    aggregate_scores,
    apply_report_rules,
    build_transcript,
    ensure_scores,
    personal_data_problems,
    verify_summary,
)
from mia.schemas import (
    AnswerScore,
    CandidateSummary,
    CompetencyScore,
    Improvement,
    InterviewPlan,
    Question,
    Report,
    SummaryPoint,
    Turn,
)

FIXTURES = Path(__file__).parent / "fixtures"


def load_plan() -> InterviewPlan:
    return InterviewPlan.model_validate_json(
        (FIXTURES / "prep" / "plan_ok.json").read_text(encoding="utf-8")
    )


def load_turns() -> list[Turn]:
    raw = json.loads((FIXTURES / "report" / "turns.json").read_text(encoding="utf-8"))
    return [Turn.model_validate(item) for item in raw]


def fixed_scorer(value: int = 2):
    calls: list[tuple[str, str]] = []

    def scorer(question: Question, answer: str) -> AnswerScore:
        calls.append((question.id, answer))
        return AnswerScore(score=value, criteria_met=[], evidence_quotes=[], justification="x")

    return scorer, calls


def scored(turns: list[Turn], *values: int | None) -> list[Turn]:
    """Replace the score of each answered turn, in order."""
    answered = iter(values)
    result = []
    for turn in turns:
        if turn.answer_text is None:
            result.append(turn)
            continue
        value = next(answered)
        score = (
            None
            if value is None
            else AnswerScore(score=value, criteria_met=[], evidence_quotes=[], justification="x")
        )
        result.append(turn.model_copy(update={"score": score}))
    return result


# ---------- ensure_scores ----------


def test_ensure_scores_fills_only_missing_answered_turns() -> None:
    plan, turns = load_plan(), load_turns()
    scorer, calls = fixed_scorer(2)

    result = ensure_scores(plan, turns, scorer)

    assert calls == [("q2", "Usei pandas para limpar os dados e Streamlit para o painel.")]
    assert result[1].score is not None and result[1].score.score == 2
    assert [t.score.score for t in result if t.score] == [4, 2, 3, 5]
    assert result[4].score is None  # closing turn has no answer
    assert turns[1].score is None  # input not mutated


def test_ensure_scores_skips_turn_when_scorer_fails() -> None:
    def broken(question: Question, answer: str) -> AnswerScore:
        raise RuntimeError("judge down")

    result = ensure_scores(load_plan(), load_turns(), broken)

    assert result[1].score is None
    assert result[0].score is not None


def test_ensure_scores_unknown_question_raises() -> None:
    turns = load_turns()
    turns[1] = turns[1].model_copy(update={"question_id": "q99"})
    scorer, _ = fixed_scorer()

    with pytest.raises(ReportError, match="q99"):
        ensure_scores(load_plan(), turns, scorer)


# ---------- aggregate_scores ----------


def test_aggregate_scores_by_competency_and_overall() -> None:
    plan = load_plan()
    # q1 (Comunicação)=4, q2 (Python)=2, q2 follow-up=3, q3 (RAG)=5
    turns = scored(load_turns(), 4, 2, 3, 5)

    competencies, overall = aggregate_scores(plan, turns)

    assert competencies == {"Comunicação de resultados": 4.0, "Python": 2.5, "RAG": 5.0}
    assert overall == 3.8  # (4 + 2.5 + 5) / 3 = 3.83


def test_aggregate_scores_ignores_unscored_turns() -> None:
    turns = scored(load_turns(), None, 2, None, 4)

    competencies, overall = aggregate_scores(load_plan(), turns)

    assert competencies == {"Python": 2.0, "RAG": 4.0}
    assert overall == 3.0


def test_aggregate_scores_without_scores_raises() -> None:
    turns = scored(load_turns(), None, None, None, None)

    with pytest.raises(ReportError):
        aggregate_scores(load_plan(), turns)


# ---------- build_transcript ----------


def test_build_transcript_masks_answers_and_skips_unanswered() -> None:
    transcript = build_transcript(load_plan(), load_turns())

    assert "ana.teste@example.com" not in transcript
    assert "98765-4321" not in transcript
    assert "[EMAIL]" in transcript and "[TELEFONE]" in transcript
    assert "Pergunta (q2): Que decisão técnica você mudaria hoje?" in transcript
    assert "terminou" not in transcript  # closing turn without answer
    assert transcript.index("(q1)") < transcript.index("(q3)")


# ---------- report rules / summary checks ----------


def make_report(overall: float = 2.0, names: tuple[str, ...] = ("A", "B"), issue_qid: str = "q1"):
    return Report(
        overall_score=overall,
        competencies=[CompetencyScore(competency=n, score=1, summary=f"s {n}") for n in names],
        strengths=["bom"],
        improvements=[Improvement(question_id=issue_qid, issue="i", stronger_answer="s")],
    )


def make_summary(
    strengths: list[str] | None = None,
    concerns: list[str] | None = None,
    headline: str = "Resposta sólida em dados.",
) -> CandidateSummary:
    def pts(quotes: list[str]) -> list[SummaryPoint]:
        return [SummaryPoint(point="p", answer_quote=q) for q in quotes]

    return CandidateSummary(
        headline=headline,
        summary="Desempenho consistente.",
        strengths=pts(strengths or ["usei pandas"]),
        concerns=pts(concerns or ["não medi o impacto"]),
        suggested_next_step="advance",
        next_step_reason="Boa base técnica.",
    )


ANSWERS = ["Eu usei pandas no projeto.", "Confesso que não medi o impacto."]


def test_apply_report_rules_overrides_numbers_and_drops_extra_competency() -> None:
    report = make_report(names=("A", "B", "C"))
    result = apply_report_rules(report, {"A": 3.5, "B": 5.0}, 4.3, {"q1"})
    assert result.overall_score == 4.3
    assert {c.competency: c.score for c in result.competencies} == {"A": 3.5, "B": 5.0}
    assert result.competencies[0].summary == "s A"


def test_apply_report_rules_missing_competency_raises() -> None:
    with pytest.raises(ReportValidationError) as exc:
        apply_report_rules(make_report(names=("A",)), {"A": 3.0, "B": 4.0}, 3.5, {"q1"})
    assert "B" in exc.value.problems[0]


def test_apply_report_rules_drops_orphan_improvement() -> None:
    result = apply_report_rules(make_report(issue_qid="q9"), {"A": 3.0, "B": 4.0}, 3.5, {"q1"})
    assert result.improvements == []


def test_verify_summary_citacao_falsa_keeps_valid_point() -> None:
    summary = make_summary(strengths=["usei pandas", "inventei isto"])
    result = verify_summary(summary, ANSWERS)
    assert [p.answer_quote for p in result.strengths] == ["usei pandas"]


def test_verify_summary_citacao_todas_falsas_raises() -> None:
    summary = make_summary(concerns=["frase inventada", "outra inventada"])
    with pytest.raises(ReportValidationError):
        verify_summary(summary, ANSWERS)


def test_personal_data_problems_pii_in_headline_and_age() -> None:
    summary = make_summary(headline="Contato [EMAIL] ok")
    summary = summary.model_copy(update={"summary": "Ela tem 32 anos e fala bem."})
    assert len(personal_data_problems(summary)) == 2


@pytest.mark.parametrize(
    "text", ["tem 32 anos", "a idade ajuda", "perfil jovem", "um homem", "a candidata"]
)
def test_personal_data_problems_age_and_gender_patterns(text: str) -> None:
    summary = make_summary().model_copy(update={"next_step_reason": text})
    assert len(personal_data_problems(summary)) == 1


def test_personal_data_problems_clean_summary_and_pronouns_allowed() -> None:
    summary = make_summary().model_copy(update={"summary": "Ela mostra domínio da ferramenta."})
    assert personal_data_problems(summary) == []


def test_personal_data_problems_checks_points_and_raw_pii() -> None:
    summary = make_summary()
    summary.strengths[0].point = "Escreva para a@b.com"
    assert len(personal_data_problems(summary)) == 1
