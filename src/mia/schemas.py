"""Pydantic schemas shared across MIA (see docs/BACKEND_SCHEMA.md)."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class RunRecord(BaseModel):
    """One line per model call in runs/<date>_<experiment>.jsonl."""

    run_id: str
    experiment: str | None
    session_id: str | None
    prompt_name: str
    prompt_version: int
    provider: Literal["bedrock", "gemini", "groq"]
    model: str
    params: dict[str, Any]
    input_hash: str
    input: dict[str, Any]  # masked variables
    output_raw: str
    output_parsed: dict[str, Any] | None
    json_valid_first_try: bool | None  # None = not applicable (free-text output)
    repaired: bool | None  # None = not applicable (free-text output)
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost_usd: float
    error: str | None
    created_at: datetime
