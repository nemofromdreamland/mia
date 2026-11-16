"""DynamoDB implementation of `SessionRepository` (tables `mia-sessions` and `mia-turns`).

DynamoDB has no float or datetime type, so models are converted to items here:
datetimes become ISO 8601 strings, floats become `Decimal`, and `None` fields are
not stored (that keeps the `by_case` GSI sparse: only sessions with `ended_at`).
"""

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Any

import boto3
from botocore.exceptions import ClientError

from mia.repositories import (
    KEY_FIELDS,
    Clock,
    RepositoryError,
    SessionConflictError,
    SessionNotFoundError,
    _utc_now,
)
from mia.schemas import Session, SessionStatus, Turn

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


def _is_conditional_failure(error: ClientError) -> bool:
    return error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException"


class DynamoSessionRepository:
    """`SessionRepository` on DynamoDB; every state change is a conditional write."""

    def __init__(self, sessions_table: Any, turns_table: Any, clock: Clock = _utc_now) -> None:
        self._sessions = sessions_table
        self._turns = turns_table
        self._clock = clock

    @classmethod
    def from_env(
        cls,
        *,
        region: str = "us-east-1",
        sessions_table: str = SESSIONS_TABLE,
        turns_table: str = TURNS_TABLE,
    ) -> "DynamoSessionRepository":
        resource = boto3.resource("dynamodb", region_name=region)
        return cls(resource.Table(sessions_table), resource.Table(turns_table))

    def create_session(self, session: Session) -> None:
        try:
            self._sessions.put_item(
                Item=session_to_item(session),
                ConditionExpression="attribute_not_exists(session_id)",
            )
        except ClientError as error:
            if _is_conditional_failure(error):
                raise SessionConflictError(f"sessão já existe: {session.session_id}") from error
            raise RepositoryError(str(error)) from error

    def get_session(self, visitor_id: str, session_id: str) -> Session:
        try:
            response = self._sessions.get_item(
                Key={"visitor_id": visitor_id, "session_id": session_id}
            )
        except ClientError as error:
            raise RepositoryError(str(error)) from error
        item = response.get("Item")
        if item is None:
            raise SessionNotFoundError(f"sessão não encontrada: {session_id}")
        return item_to_session(item)

    def update_session(
        self,
        visitor_id: str,
        session_id: str,
        *,
        expected_status: SessionStatus,
        changes: Mapping[str, Any],
    ) -> Session:
        forbidden = KEY_FIELDS & changes.keys()
        if forbidden:
            raise ValueError(f"campos não podem ser alterados: {sorted(forbidden)}")
        current = self.get_session(visitor_id, session_id)
        data = {**current.model_dump(), **changes, "updated_at": self._clock()}
        updated = Session.model_validate(data)  # raises ValidationError (a ValueError)
        try:
            response = self._sessions.update_item(
                Key={"visitor_id": visitor_id, "session_id": session_id},
                **_update_args(session_to_item(current), session_to_item(updated), expected_status),
                ReturnValues="ALL_NEW",
            )
        except ClientError as error:
            if not _is_conditional_failure(error):
                raise RepositoryError(str(error)) from error
            # The condition failed: the session vanished or its status changed.
            actual = self.get_session(visitor_id, session_id)
            raise SessionConflictError(
                f"status atual {actual.status!r}, esperado {expected_status!r}"
            ) from error
        return item_to_session(response["Attributes"])


def _update_args(
    before: Mapping[str, Any], after: Mapping[str, Any], expected_status: str
) -> dict[str, Any]:
    """SET changed fields, REMOVE the ones that became None, guarded by the status."""
    names: dict[str, str] = {"#status": "status"}
    values: dict[str, Any] = {":expected": expected_status}
    sets: list[str] = []
    for index, (field, value) in enumerate(after.items()):
        if field in KEY_FIELDS - {"updated_at"} or before.get(field) == value:
            continue
        names[f"#f{index}"] = field
        values[f":v{index}"] = value
        sets.append(f"#f{index} = :v{index}")
    removes = []
    for index, field in enumerate(before.keys() - after.keys()):
        names[f"#r{index}"] = field
        removes.append(f"#r{index}")
    expression = "SET " + ", ".join(sets)
    if removes:
        expression += " REMOVE " + ", ".join(removes)
    return {
        "UpdateExpression": expression,
        "ConditionExpression": "attribute_exists(session_id) AND #status = :expected",
        "ExpressionAttributeNames": names,
        "ExpressionAttributeValues": values,
    }
