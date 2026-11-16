"""Mask personal data before any text is stored or sent to a model.

Pure functions (text -> text), no I/O and no logging of the original text.
"""

import re
from typing import Final

EMAIL: Final = "[EMAIL]"
PHONE: Final = "[TELEFONE]"
CPF: Final = "[CPF]"
URL: Final = "[URL]"
NAME: Final = "[NOME]"

_EMAIL_RE: Final = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Profile URLs on social/code networks, with or without scheme/www/subdomain.
# The lookbehind stops matches inside other words, paths or e-mails (box.com, /x.com).
_URL_RE: Final = re.compile(
    r"(?<![\w.@/-])(?:https?://)?(?:[\w-]+\.)*"
    r"(?:linkedin\.com|github\.com|gitlab\.com|behance\.net|instagram\.com"
    r"|facebook\.com|twitter\.com|x\.com|medium\.com)(?![\w-])"
    r"(?:/[\w\-./%~?=&#+@]*[\w\-/%~=&#+])?"
)
# 11 digits, optionally formatted as 000.000.000-00; checked before phones.
_CPF_RE: Final = re.compile(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)")
# Optional +55, DDD (2 digits, optionally in parentheses), optional mobile 9, 4 + 4 digits.
_PHONE_RE: Final = re.compile(
    r"(?<![\w+])(?:\+55[\s.-]?)?(?:\(\d{2}\)|\d{2})[\s.-]?(?:9[\s.-]?)?\d{4}[\s.-]?\d{4}(?!\w)"
)
# Any URL/domain; only applied to the first lines of a CV (own site in the header).
_ANY_URL_RE: Final = re.compile(r"(?<![\w.@/-])(?:https?://)?(?:[\w-]+\.)+[^\W\d_]{2,}(?:/\S*)?")
_HEADER_LINES: Final = 5
_PARTICLES: Final = frozenset({"da", "de", "do", "dos", "das", "e"})
_NAME_WORD_RE: Final = re.compile(r"[^\W\d_]+")


def mask_text(text: str) -> str:
    """Replace e-mails, personal URLs, CPFs and Brazilian phones with placeholders."""
    text = _EMAIL_RE.sub(EMAIL, text)
    text = _URL_RE.sub(URL, text)
    text = _CPF_RE.sub(CPF, text)
    return _PHONE_RE.sub(PHONE, text)


def extract_header_name(cv_text: str) -> str | None:
    """Return the first non-empty line if it looks like a name (2-5 letter-only words)."""
    line = next((ln.strip() for ln in cv_text.splitlines() if ln.strip()), "")
    words = line.split()
    if not 2 <= len(words) <= 5:
        return None
    if not all(_NAME_WORD_RE.fullmatch(w) for w in words):
        return None
    return " ".join(words)


def mask_name(text: str, name: str) -> str:
    """Replace the full name, then each proper word (3+ letters, no particles)."""
    words = name.split()
    full = r"\s+".join(re.escape(w) for w in words)
    text = re.sub(rf"\b{full}\b", NAME, text, flags=re.IGNORECASE)
    for word in words:
        if len(word) >= 3 and word.lower() not in _PARTICLES:
            text = re.sub(rf"\b{re.escape(word)}\b", NAME, text, flags=re.IGNORECASE)
    return text


def mask_cv(cv_text: str) -> str:
    """Mask a CV: contacts, own site in the header and the header name everywhere."""
    name = extract_header_name(cv_text)
    lines = mask_text(cv_text).split("\n")
    head = _ANY_URL_RE.sub(URL, "\n".join(lines[:_HEADER_LINES]))
    text = "\n".join([head, *lines[_HEADER_LINES:]])
    return mask_name(text, name) if name else text
