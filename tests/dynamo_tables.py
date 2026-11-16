"""Creates the `mia-sessions` and `mia-turns` tables (with GSI `by_case`) in moto."""

from typing import Any

from mia.repo_dynamo import BY_CASE_INDEX, SESSIONS_TABLE, TURNS_TABLE


def create_tables(resource: Any) -> tuple[Any, Any]:
    sessions = resource.create_table(
        TableName=SESSIONS_TABLE,
        BillingMode="PAY_PER_REQUEST",
        KeySchema=[
            {"AttributeName": "visitor_id", "KeyType": "HASH"},
            {"AttributeName": "session_id", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "visitor_id", "AttributeType": "S"},
            {"AttributeName": "session_id", "AttributeType": "S"},
            {"AttributeName": "case_id", "AttributeType": "S"},
            {"AttributeName": "ended_at", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": BY_CASE_INDEX,
                "KeySchema": [
                    {"AttributeName": "case_id", "KeyType": "HASH"},
                    {"AttributeName": "ended_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
    )
    turns = resource.create_table(
        TableName=TURNS_TABLE,
        BillingMode="PAY_PER_REQUEST",
        KeySchema=[
            {"AttributeName": "session_id", "KeyType": "HASH"},
            {"AttributeName": "turn_no", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "session_id", "AttributeType": "S"},
            {"AttributeName": "turn_no", "AttributeType": "N"},
        ],
    )
    return sessions, turns
