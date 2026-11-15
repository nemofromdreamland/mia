"""Task 0.7: send one message to the AgentCore WebSocket echo runtime and check the echo.

Usage:
    uv run python scripts/agentcore_echo_client.py --arn <runtime ARN> [--profile mia]
        [--region us-east-1] [--message "texto"]

Exit codes: 0 echo matched, 1 mismatch or connection error, 2 invalid argument.
"""

import argparse
import asyncio
import json
import re
import sys
import time
from collections.abc import Callable
from typing import Any

import boto3
import websockets
from bedrock_agentcore.runtime import AgentCoreRuntimeClient
from pydantic import BaseModel

ARN_RE = re.compile(r"^arn:aws:bedrock-agentcore:[a-z0-9-]+:\d{12}:runtime/[A-Za-z0-9_-]+$")
SIGV4_PARAM_RE = re.compile(r"(X-Amz-[A-Za-z-]+)=[^&\s'\"]+")
DEFAULT_MESSAGE = "Olá, AgentCore! Teste de eco da tarefa 0.7."

Connect = Callable[[str], Any]


class EchoResult(BaseModel):
    sent: str
    received: str | None
    matched: bool
    latency_ms: int
    error: str | None = None


def parse_runtime_arn(arn: str) -> str:
    """Return the ARN unchanged if it looks like an AgentCore runtime ARN."""
    if not ARN_RE.match(arn):
        raise ValueError(f"ARN de runtime inválido: {arn!r}")
    return arn


def build_signed_ws_url(arn: str, region: str, session: boto3.Session, expires_s: int = 300) -> str:
    """Presigned (SigV4 in the query string) wss:// URL, the same way the voice Lambda will."""
    runtime_client = AgentCoreRuntimeClient(region=region, session=session)
    return runtime_client.generate_presigned_url(runtime_arn=arn, expires=expires_s)


def redact(text: str) -> str:
    """Hide SigV4 query values in case an error message echoes the signed URL."""
    return SIGV4_PARAM_RE.sub(r"\1=***", text)


async def echo_once(url: str, message: str, connect: Connect = websockets.connect) -> EchoResult:
    """Send {"inputText": message} and compare it with the server's {"echo": {...}} reply."""
    start = time.perf_counter()
    try:
        async with connect(url) as ws:
            await ws.send(json.dumps({"inputText": message}))
            raw = await ws.recv()
        received = json.loads(raw)["echo"]["inputText"]
    except Exception as exc:  # report any failure as data, never crash
        elapsed = int((time.perf_counter() - start) * 1000)
        error = redact(f"{type(exc).__name__}: {exc}")
        return EchoResult(
            sent=message, received=None, matched=False, latency_ms=elapsed, error=error
        )
    elapsed = int((time.perf_counter() - start) * 1000)
    return EchoResult(
        sent=message, received=received, matched=received == message, latency_ms=elapsed
    )


def main(
    argv: list[str] | None = None,
    connect: Connect = websockets.connect,
    session: boto3.Session | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="AgentCore WebSocket echo check (task 0.7)")
    parser.add_argument("--arn", required=True, help="runtime ARN (agentcore status --json)")
    parser.add_argument("--profile", default="mia")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--message", default=DEFAULT_MESSAGE)
    args = parser.parse_args(argv)

    try:
        arn = parse_runtime_arn(args.arn)
    except ValueError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 2

    session = session or boto3.Session(profile_name=args.profile, region_name=args.region)
    url = build_signed_ws_url(arn, args.region, session)
    result = asyncio.run(echo_once(url, args.message, connect=connect))

    print(f"sent:     {result.sent}")
    print(f"received: {result.received}")
    print(f"matched: {result.matched}")
    print(f"latency_ms: {result.latency_ms}")
    if result.error:
        print(f"error: {result.error}")
    return 0 if result.matched else 1


if __name__ == "__main__":
    sys.exit(main())
