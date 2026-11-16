"""Deterministic checks on LLM output ("the LLM drafts; the code decides").

Literal quotes: a quote the model cites (cv_quote, evidence_quotes, answer_quote) must
exist in the source text. Only cosmetic differences are forgiven: Unicode form, curly
vs straight quotes and runs of whitespace. Case and punctuation must match.
"""

import re
import unicodedata
from collections.abc import Sequence

_QUOTE_CHARS = str.maketrans({"“": '"', "”": '"', "„": '"', "‘": "'", "’": "'", "‚": "'"})
_WHITESPACE = re.compile(r"\s+")


def normalize_for_quote(text: str) -> str:
    """NFC, straight quotes, single spaces, trimmed. Applied to both quote and source."""
    text = unicodedata.normalize("NFC", text).translate(_QUOTE_CHARS)
    return _WHITESPACE.sub(" ", text).strip()


def quote_in_source(quote: str, source: str) -> bool:
    """True when the (normalized) quote appears literally in the (normalized) source."""
    needle = normalize_for_quote(quote)
    return bool(needle) and needle in normalize_for_quote(source)


def unverified_quotes(quotes: Sequence[str], source: str) -> list[str]:
    """Quotes not found in the source, in their original order."""
    return [quote for quote in quotes if not quote_in_source(quote, source)]
