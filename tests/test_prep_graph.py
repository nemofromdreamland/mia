from pathlib import Path

import pytest
from pdf_helper import make_text_pdf, write_text_pdf

from mia.prep_graph import PrepError, extract_cv_text

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
