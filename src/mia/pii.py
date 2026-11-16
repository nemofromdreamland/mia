"""Mask personal data before any text is stored or sent to a model.

Pure functions (text -> text), no I/O and no logging of the original text.
"""

import re
from typing import Final

EMAIL: Final = "[EMAIL]"
PHONE: Final = "[TELEFONE]"
CPF: Final = "[CPF]"

_EMAIL_RE: Final = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# 11 digits, optionally formatted as 000.000.000-00; checked before phones.
_CPF_RE: Final = re.compile(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)")
# Optional +55, DDD (2 digits, optionally in parentheses), optional mobile 9, 4 + 4 digits.
_PHONE_RE: Final = re.compile(
    r"(?<![\w+])(?:\+55[\s.-]?)?(?:\(\d{2}\)|\d{2})[\s.-]?(?:9[\s.-]?)?\d{4}[\s.-]?\d{4}(?!\w)"
)


def mask_text(text: str) -> str:
    """Replace e-mails, CPFs and Brazilian phone numbers with placeholders."""
    text = _EMAIL_RE.sub(EMAIL, text)
    text = _CPF_RE.sub(CPF, text)
    return _PHONE_RE.sub(PHONE, text)
