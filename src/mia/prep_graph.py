"""Preparation graph: CV file -> text -> masked -> screening -> plan -> coverage checks.

Used offline (case fixtures) and by the CLI; the web never uploads CVs.
"""

from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

_TEXT_SUFFIXES = {".md", ".txt"}


class PrepError(Exception):
    """Preparation could not start or finish (bad input file, failed checks)."""


def _read_pdf(path: Path) -> str:
    try:
        reader = PdfReader(path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except (PdfReadError, OSError, ValueError) as exc:
        raise PrepError(f"{path}: não foi possível ler o PDF ({exc})") from exc


def extract_cv_text(path: Path) -> str:
    """Return the CV text from a .pdf, .md or .txt file; raise PrepError otherwise."""
    suffix = path.suffix.lower()
    if suffix != ".pdf" and suffix not in _TEXT_SUFFIXES:
        raise PrepError(f"{path}: formato não suportado (use .pdf, .md ou .txt)")
    if not path.is_file():
        raise PrepError(f"{path}: arquivo não encontrado")
    text = _read_pdf(path) if suffix == ".pdf" else path.read_text(encoding="utf-8")
    if not text.strip():
        raise PrepError(f"{path}: o CV não tem texto")
    return text
