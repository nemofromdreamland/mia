"""Mask personal data before any text is stored or sent to a model.

Pure functions (text -> text), no I/O and no logging of the original text.
"""

import re
from typing import Final

EMAIL: Final = "[EMAIL]"
PHONE: Final = "[TELEFONE]"
CPF: Final = "[CPF]"
URL: Final = "[URL]"

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


def mask_text(text: str) -> str:
    """Replace e-mails, personal URLs, CPFs and Brazilian phones with placeholders."""
    text = _EMAIL_RE.sub(EMAIL, text)
    text = _URL_RE.sub(URL, text)
    text = _CPF_RE.sub(CPF, text)
    return _PHONE_RE.sub(PHONE, text)
