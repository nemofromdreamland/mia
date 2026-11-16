from pathlib import Path

import pytest

from mia.checks import normalize_for_quote, quote_in_source, unverified_quotes


@pytest.mark.parametrize(
    ("quote", "source"),
    [
        ("usei FastAPI", "Eu usei FastAPI no TCC."),
        ("usei  FastAPI", "usei\nFastAPI"),
        ("o “cache”", 'o "cache"'),
        ("it’s fine", "it's fine"),
        ("café", "café"),  # NFC: composed vs decomposed accent
    ],
)
def test_quote_found(quote: str, source: str) -> None:
    assert quote_in_source(quote, source) is True


@pytest.mark.parametrize(
    ("case", "quote", "source"),
    [
        ("invented", "liderei 10 pessoas", "Eu usei FastAPI no TCC."),
        ("paraphrase", "utilizei FastAPI", "usei FastAPI"),
        ("case", "fastapi", "FastAPI"),
        ("punctuation", "FastAPI, no TCC", "FastAPI no TCC"),
    ],
)
def test_quote_not_found(case: str, quote: str, source: str) -> None:
    assert quote_in_source(quote, source) is False


@pytest.mark.parametrize("quote", ["", "   ", "\n\t"])
def test_empty_quote_is_not_evidence(quote: str) -> None:
    assert quote_in_source(quote, "qualquer texto") is False


def test_unverified_quotes_keeps_order() -> None:
    source = "Eu usei FastAPI no TCC."
    quotes = ["usei FastAPI", "inventado", "TCC", "  ", "outro inventado"]
    assert unverified_quotes(quotes, source) == ["inventado", "  ", "outro inventado"]


def test_unverified_quotes_empty_list() -> None:
    assert unverified_quotes([], "texto") == []


def test_normalize_for_quote() -> None:
    assert normalize_for_quote("  a\n\n“b”\t ‘c’  ") == "a \"b\" 'c'"


def test_checks_does_not_import_llm_or_sdk() -> None:
    source = (Path(__file__).resolve().parents[1] / "src" / "mia" / "checks.py").read_text(
        encoding="utf-8"
    )
    for forbidden in ("mia.llm", "langchain", "from mia import llm"):
        assert forbidden not in source
