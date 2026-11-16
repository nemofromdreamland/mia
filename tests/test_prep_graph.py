import json
from pathlib import Path

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from pdf_helper import make_text_pdf, write_text_pdf

from mia.llm import LLMInvalidOutputError
from mia.prep_graph import (
    PrepError,
    PrepInput,
    PrepResult,
    PrepValidationError,
    build_prep_graph,
    check_plan_coverage,
    check_screening_quotes,
    extract_cv_text,
    run_prep,
)
from mia.schemas import InterviewPlan, Screening

FIXTURES = Path(__file__).parent / "fixtures" / "prep"
CV_PDF = FIXTURES / "cv_ficticio.pdf"
CV_MD = FIXTURES / "cv_ficticio.md"


def _pdf_pages() -> list[str]:
    """The committed PDF = cv_ficticio.md split in 2 pages at 'Projetos'."""
    text = CV_MD.read_text(encoding="utf-8")
    first, second = text.split("Projetos", 1)
    return [first, "Projetos" + second]


def test_committed_pdf_matches_markdown_source() -> None:
    assert CV_PDF.read_bytes() == make_text_pdf(_pdf_pages())


def test_pdf_extracts_all_pages_in_order() -> None:
    text = extract_cv_text(CV_PDF)
    first = text.index("Analista de dados júnior")
    second = text.index("Chatbot de FAQ com RAG")
    assert first < second
    assert "Universidade Imaginária" in text


def test_markdown_is_read_as_is() -> None:
    assert extract_cv_text(CV_MD) == CV_MD.read_text(encoding="utf-8")


def test_txt_is_read_as_is(tmp_path: Path) -> None:
    path = tmp_path / "cv.txt"
    path.write_text("Formação: Ciência da Computação\n", encoding="utf-8")
    assert extract_cv_text(path) == "Formação: Ciência da Computação\n"


def test_extension_is_case_insensitive(tmp_path: Path) -> None:
    path = write_text_pdf(tmp_path / "CV.PDF", ["Experiência em Python"])
    assert "Experiência em Python" in extract_cv_text(path)


@pytest.mark.parametrize("name", ["cv.docx", "cv", "cv.pdf.bak"])
def test_unsupported_extension_raises(tmp_path: Path, name: str) -> None:
    path = tmp_path / name
    path.write_text("qualquer coisa", encoding="utf-8")
    with pytest.raises(PrepError, match=name.replace(".", r"\.")):
        extract_cv_text(path)


def test_pdf_without_text_raises(tmp_path: Path) -> None:
    path = write_text_pdf(tmp_path / "vazio.pdf", ["   "])
    with pytest.raises(PrepError, match="vazio.pdf"):
        extract_cv_text(path)


def test_blank_markdown_raises(tmp_path: Path) -> None:
    path = tmp_path / "branco.md"
    path.write_text(" \n\t\n", encoding="utf-8")
    with pytest.raises(PrepError, match="branco.md"):
        extract_cv_text(path)


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(PrepError, match="nao_existe.pdf"):
        extract_cv_text(tmp_path / "nao_existe.pdf")


def test_corrupt_pdf_raises(tmp_path: Path) -> None:
    path = tmp_path / "quebrado.pdf"
    path.write_bytes(b"isto nao e um pdf")
    with pytest.raises(PrepError, match="quebrado.pdf"):
        extract_cv_text(path)


# ---------- validations (R6, R8) ----------

SCREENING_JSON = FIXTURES / "screening_ok.json"
PLAN_JSON = FIXTURES / "plan_ok.json"


def _screening() -> Screening:
    return Screening.model_validate_json(SCREENING_JSON.read_text(encoding="utf-8"))


def _plan() -> InterviewPlan:
    return InterviewPlan.model_validate_json(PLAN_JSON.read_text(encoding="utf-8"))


def test_check_quotes_ok() -> None:
    cv = CV_MD.read_text(encoding="utf-8")
    assert check_screening_quotes(_screening(), cv) == []


def test_check_quotes_reports_invented_quote_in_strengths_and_concerns() -> None:
    screening = _screening()
    screening.strengths[0].cv_quote = "Liderei uma equipe de 50 pessoas"
    screening.concerns[0].cv_quote = "Nunca trabalhou com dados"
    problems = check_screening_quotes(screening, CV_MD.read_text(encoding="utf-8"))
    assert len(problems) == 2
    assert "Liderei uma equipe de 50 pessoas" in problems[0]
    assert "Nunca trabalhou com dados" in problems[1]


def test_check_coverage_ok() -> None:
    assert check_plan_coverage(_screening(), _plan(), "technical") == []


def test_check_coverage_competency_without_question() -> None:
    screening = _screening()
    screening.competencies.append("Estatística")
    problems = check_plan_coverage(screening, _plan(), "technical")
    assert len(problems) == 1
    assert "Estatística" in problems[0]


def test_check_coverage_no_question_targets_a_concern() -> None:
    plan = _plan()
    for question in plan.questions:
        question.targets_concern = None
    problems = check_plan_coverage(_screening(), plan, "technical")
    assert len(problems) == 1
    assert "targets_concern" in problems[0]


def test_check_coverage_wrong_persona() -> None:
    problems = check_plan_coverage(_screening(), _plan(), "hr")
    assert len(problems) == 1
    assert "hr" in problems[0] and "technical" in problems[0]


def test_check_coverage_duplicate_ids() -> None:
    plan = _plan()
    plan.questions[1].id = "q1"
    problems = check_plan_coverage(_screening(), plan, "technical")
    assert len(problems) == 1
    assert "q1" in problems[0]


def test_check_coverage_reports_all_problems_not_just_first() -> None:
    screening = _screening()
    screening.competencies.append("Estatística")
    plan = _plan()
    plan.questions[1].id = "q1"
    assert len(check_plan_coverage(screening, plan, "hr")) == 3


# ---------- graph (R4, R5, R7, R9-R12) ----------

JOB = "Vaga fictícia: Analista de Dados Júnior na Empresa Imaginária. Contato: rh@exemplo.com"


def _fake(*replies: str) -> GenericFakeChatModel:
    return GenericFakeChatModel(messages=iter([AIMessage(content=r) for r in replies]))


def _ok_replies() -> tuple[str, str]:
    return SCREENING_JSON.read_text(encoding="utf-8"), PLAN_JSON.read_text(encoding="utf-8")


def _input(cv_path: Path = CV_MD) -> PrepInput:
    return PrepInput(
        cv_path=cv_path,
        job_text=JOB,
        persona="technical",
        level="junior",
        estimated_minutes=15,
    )


def _records(runs_dir: Path) -> list[dict]:
    lines = [
        line
        for file in sorted(runs_dir.glob("*.jsonl"))
        for line in file.read_text(encoding="utf-8").splitlines()
    ]
    return [json.loads(line) for line in lines if line]


def test_feliz_completo_with_pdf(tmp_path: Path) -> None:
    result = run_prep(
        _input(CV_PDF),
        chat_model=_fake(*_ok_replies()),
        runs_dir=tmp_path,
        session_id="s1",
        experiment="t",
    )
    assert isinstance(result, PrepResult)
    assert result.screening.job_title == "Analista de Dados Júnior"
    assert result.plan.persona == "technical"
    records = _records(tmp_path)
    assert [r["prompt_name"] for r in records] == ["screening", "planner"]
    assert {r["session_id"] for r in records} == {"s1"}


def test_models_never_see_personal_data(tmp_path: Path) -> None:
    run_prep(_input(), chat_model=_fake(*_ok_replies()), runs_dir=tmp_path)
    raw = json.dumps(_records(tmp_path), ensure_ascii=False)
    for personal in ["bruna.lopes@exemplo.com.br", "98765-4321", "Bruna", "rh@exemplo.com"]:
        assert personal not in raw
    assert "[EMAIL]" in raw


def test_planner_receives_screening_json_and_request(tmp_path: Path) -> None:
    run_prep(_input(), chat_model=_fake(*_ok_replies()), runs_dir=tmp_path)
    planner = _records(tmp_path)[1]["input"]
    assert planner["persona"] == "technical"
    assert planner["level"] == "junior"
    assert planner["estimated_minutes"] == "15"
    assert json.loads(planner["screening"])["fit_score"] == 72


def test_invented_quote_raises_with_artifacts(tmp_path: Path) -> None:
    screening = json.loads(_ok_replies()[0])
    screening["strengths"][0]["cv_quote"] = "Liderei uma equipe de 50 pessoas"
    fake = _fake(json.dumps(screening), _ok_replies()[1])
    with pytest.raises(PrepValidationError) as info:
        run_prep(_input(), chat_model=fake, runs_dir=tmp_path)
    assert "Liderei uma equipe de 50 pessoas" in info.value.problems[0]
    assert info.value.screening is not None
    assert info.value.plan is not None


def test_several_problems_are_all_reported(tmp_path: Path) -> None:
    screening = json.loads(_ok_replies()[0])
    screening["strengths"][0]["cv_quote"] = "Citação inventada"
    screening["competencies"].append("Estatística")
    fake = _fake(json.dumps(screening), _ok_replies()[1])
    with pytest.raises(PrepValidationError) as info:
        run_prep(_input(), chat_model=fake, runs_dir=tmp_path)
    assert len(info.value.problems) == 2


def test_invalid_screening_stops_before_planner(tmp_path: Path) -> None:
    fake = _fake("não é json", "ainda não")
    with pytest.raises(LLMInvalidOutputError):
        run_prep(_input(), chat_model=fake, runs_dir=tmp_path)
    assert [r["prompt_name"] for r in _records(tmp_path)] == ["screening"]


def test_bad_cv_file_fails_without_calling_model(tmp_path: Path) -> None:
    path = tmp_path / "cv.docx"
    path.write_text("x", encoding="utf-8")
    with pytest.raises(PrepError, match=r"cv\.docx"):
        run_prep(_input(path), chat_model=_fake(), runs_dir=tmp_path)
    assert _records(tmp_path) == []


def test_build_prep_graph_has_the_five_nodes() -> None:
    graph = build_prep_graph(chat_model=_fake())
    assert {"extract", "mask", "screen", "plan", "validate"} <= set(graph.get_graph().nodes)
