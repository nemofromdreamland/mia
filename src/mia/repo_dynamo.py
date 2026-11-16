"""DynamoDB implementation of `SessionRepository` (tables `mia-sessions` and `mia-turns`).

DynamoDB has no float or datetime type, so models are converted to items here:
datetimes become ISO 8601 strings, floats become `Decimal`, and `None` fields are
not stored (that keeps the `by_case` GSI sparse: only sessions with `ended_at`).
"""

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Any

from mia.schemas import Session, Turn

SESSIONS_TABLE = "mia-sessions"
TURNS_TABLE = "mia-turns"
BY_CASE_INDEX = "by_case"


def _to_dynamo(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, Mapping):
        return {k: _to_dynamo(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_to_dynamo(v) for v in value]
    return value


def _from_dynamo(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, Mapping):
        return {k: _from_dynamo(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_from_dynamo(v) for v in value]
    return value


def session_to_item(session: Session) -> dict[str, Any]:
    return _to_dynamo(session.model_dump())


def item_to_session(item: Mapping[str, Any]) -> Session:
    return Session.model_validate(_from_dynamo(item))


def turn_to_item(turn: Turn) -> dict[str, Any]:
    return _to_dynamo(turn.model_dump())


def item_to_turn(item: Mapping[str, Any]) -> Turn:
    return Turn.model_validate(_from_dynamo(item))
