import pytest

from mia.pii import mask_text


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
