"""X-Visitor-Id validation (UUID v4); the visitor never comes from the body."""

import uuid

from fastapi import Header

from mia.service import ServiceError


def parse_visitor_id(value: str | None) -> str:
    """Return the canonical lowercase UUID v4 or raise `invalid_input`."""
    try:
        parsed = uuid.UUID(value or "")
    except ValueError:
        parsed = None
    if parsed is None or parsed.version != 4 or str(parsed) != (value or "").lower():
        raise ServiceError("invalid_input", "X-Visitor-Id ausente ou inválido.")
    return str(parsed)


def visitor_id_header(x_visitor_id: str | None = Header(default=None)) -> str:
    return parse_visitor_id(x_visitor_id)
