from pathlib import Path

import pytest

from mia.pii import extract_header_name, mask_cv, mask_name, mask_text


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("contato: ana.souza@exemplo.com.br", "contato: [EMAIL]"),
        ("ana+mia@ex.io", "[EMAIL]"),
        ("(11) 98765-4321", "[TELEFONE]"),
        ("+55 11 3456-7890", "[TELEFONE]"),
        ("ligue 11 3456.7890 hoje", "ligue [TELEFONE] hoje"),
        ("11987654321", "[CPF]"),
        ("CPF 123.456.789-09", "CPF [CPF]"),
        ("cel: 21 9 8765-4321", "cel: [TELEFONE]"),
    ],
)
def test_masks_personal_data(text: str, expected: str) -> None:
    assert mask_text(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("linkedin.com/in/ana-souza", "[URL]"),
        ("https://github.com/anasouza", "[URL]"),
        ("https://www.linkedin.com/in/ana-souza/.", "[URL]."),
        ("GitHub: github.com/anasouza, Insta: instagram.com/ana", "GitHub: [URL], Insta: [URL]"),
        ("https://twitter.com/ana e x.com/ana", "[URL] e [URL]"),
        ("https://ana.medium.com/post-1", "[URL]"),
    ],
)
def test_masks_personal_urls(text: str, expected: str) -> None:
    assert mask_text(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "veja https://docs.python.org/3/",
        "baixe de https://box.com/arquivo",
        "https://example.com/github.com-guide",
    ],
)
def test_keeps_non_personal_urls(text: str) -> None:
    assert mask_text(text) == text


@pytest.mark.parametrize(
    "text",
    [
        "2019–2023, Python 3.12, R$ 8.500,00, 35%",
        "Reduzi a latência de 1200 ms para 300 ms.\nUsei FastAPI e pytest.",
        "",
    ],
)
def test_keeps_text_without_personal_data(text: str) -> None:
    assert mask_text(text) == text


def test_is_idempotent() -> None:
    text = "ana@ex.com, (11) 98765-4321, 123.456.789-09"
    once = mask_text(text)
    assert mask_text(once) == once
    assert once == "[EMAIL], [TELEFONE], [CPF]"


CV = "Ana Beatriz de Souza\nDesenvolvedora Python\nAna liderou o time. Souza é sênior.\n"


@pytest.mark.parametrize(
    ("cv", "expected"),
    [
        ("Ana Beatriz de Souza\nPython", "Ana Beatriz de Souza"),
        ("\n\n  Ana Souza  \nPython", "Ana Souza"),
        ("Currículo\nana@ex.com", None),
        ("Ana Souza 2024", None),
        ("ana@ex.com\nAna Souza", None),
        ("Um Dois Tres Quatro Cinco Seis", None),
        ("", None),
    ],
)
def test_extract_header_name(cv: str, expected: str | None) -> None:
    assert extract_header_name(cv) == expected


def test_mask_name_full_and_words_case_insensitive() -> None:
    out = mask_name("ANA Beatriz de Souza falou. ana disse que de nada.", "Ana Beatriz de Souza")
    assert out == "[NOME] falou. [NOME] disse que de nada."


def test_mask_cv_masks_name_everywhere() -> None:
    assert mask_cv(CV) == "[NOME]\nDesenvolvedora Python\n[NOME] liderou o time. [NOME] é sênior.\n"


def test_mask_cv_without_name_header_still_masks_contacts() -> None:
    assert mask_cv("Currículo\nana@ex.com") == "Currículo\n[EMAIL]"


def test_mask_cv_masks_own_site_only_in_header() -> None:
    cv = "Ana Souza\nwww.ana.dev\n1\n2\n3\n4\nVeja https://docs.python.org/3/"
    assert mask_cv(cv) == "[NOME]\n[URL]\n1\n2\n3\n4\nVeja https://docs.python.org/3/"


def test_mask_cv_is_idempotent_and_empty() -> None:
    assert mask_cv(mask_cv(CV)) == mask_cv(CV)
    assert mask_cv("") == ""


def test_cv_example_has_no_personal_data() -> None:
    base = Path(__file__).parent / "fixtures" / "pii"
    out = mask_cv((base / "cv_example.md").read_text(encoding="utf-8")).lower()
    values = (base / "cv_example_pii.txt").read_text(encoding="utf-8").splitlines()
    assert [v for v in values if v and v.lower() in out] == []
    assert "R$ 8.500,00" in out.upper() and "3.12" in out
