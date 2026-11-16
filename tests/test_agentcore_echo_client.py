"""Offline tests for scripts/agentcore_echo_client.py (no network, fake credentials)."""

import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import boto3
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "agentcore_echo_client.py"
spec = importlib.util.spec_from_file_location("agentcore_echo_client", SCRIPT)
assert spec and spec.loader
client = importlib.util.module_from_spec(spec)
sys.modules["agentcore_echo_client"] = client
spec.loader.exec_module(client)

ARN = "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/echo_default_agent-abc123"
FAKE_SECRET = "FAKESECRETKEYdoNotPrintThis0123456789"


def fake_session() -> boto3.Session:
    return boto3.Session(
        aws_access_key_id="AKIAFAKEFAKEFAKE",
        aws_secret_access_key=FAKE_SECRET,
        region_name="us-east-1",
    )


class FakeWs:
    """Minimal async context manager that mimics a websockets connection."""

    def __init__(self, reply: Any = None, fail: Exception | None = None) -> None:
        self.reply = reply
        self.fail = fail
        self.sent: list[str] = []

    async def __aenter__(self) -> "FakeWs":
        if self.fail:
            raise self.fail
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def send(self, data: str) -> None:
        self.sent.append(data)

    async def recv(self) -> str:
        if self.reply is None:
            payload = json.loads(self.sent[-1])
            return json.dumps({"echo": payload})
        return self.reply


def make_connect(ws: FakeWs):
    def connect(url: str) -> FakeWs:
        return ws

    return connect


@pytest.mark.parametrize("arn", [ARN, "arn:aws:bedrock-agentcore:us-west-2:000000000000:runtime/x"])
def test_parse_runtime_arn_valid(arn: str) -> None:
    assert client.parse_runtime_arn(arn) == arn


@pytest.mark.parametrize(
    "arn",
    ["", "foo", "arn:aws:s3:::bucket", "arn:aws:bedrock-agentcore:us-east-1:123:runtime/x"],
)
def test_parse_runtime_arn_invalid(arn: str) -> None:
    with pytest.raises(ValueError):
        client.parse_runtime_arn(arn)


def test_build_signed_ws_url_has_sigv4_and_no_secret() -> None:
    url = client.build_signed_ws_url(ARN, "us-east-1", fake_session())
    assert url.startswith("wss://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/")
    assert "X-Amz-Signature=" in url
    assert "X-Amz-Expires=300" in url
    assert FAKE_SECRET not in url


def test_echo_once_matched() -> None:
    result = asyncio.run(client.echo_once("wss://x", "olá", connect=make_connect(FakeWs())))
    assert result.matched is True
    assert result.received == "olá"
    assert result.error is None
    assert result.latency_ms >= 0


def test_echo_once_mismatch() -> None:
    ws = FakeWs(reply=json.dumps({"echo": {"inputText": "outra coisa"}}))
    result = asyncio.run(client.echo_once("wss://x", "olá", connect=make_connect(ws)))
    assert result.matched is False
    assert result.received == "outra coisa"


def test_echo_once_connection_error() -> None:
    ws = FakeWs(fail=OSError("handshake failed"))
    result = asyncio.run(client.echo_once("wss://x", "olá", connect=make_connect(ws)))
    assert result.matched is False
    assert result.received is None
    assert result.error and "handshake failed" in result.error


def test_main_invalid_arn_exits_2_without_network(capsys: pytest.CaptureFixture[str]) -> None:
    def boom(url: str) -> FakeWs:
        raise AssertionError("network must not be called")

    assert client.main(["--arn", "foo"], connect=boom, session=fake_session()) == 2
    assert "ARN" in capsys.readouterr().err


def test_main_missing_arn_exits_2() -> None:
    with pytest.raises(SystemExit) as exc:
        client.main([], session=fake_session())
    assert exc.value.code == 2


def test_main_echo_ok_exits_0(capsys: pytest.CaptureFixture[str]) -> None:
    code = client.main(["--arn", ARN], connect=make_connect(FakeWs()), session=fake_session())
    out = capsys.readouterr().out
    assert code == 0
    assert "matched: True" in out
    assert FAKE_SECRET not in out
    assert "X-Amz-Signature" not in out


def test_main_mismatch_exits_1() -> None:
    ws = FakeWs(reply=json.dumps({"echo": {"inputText": "x"}}))
    assert client.main(["--arn", ARN], connect=make_connect(ws), session=fake_session()) == 1


def test_main_error_with_signed_url_is_redacted(capsys: pytest.CaptureFixture[str]) -> None:
    signed_url = client.build_signed_ws_url(ARN, "us-east-1", fake_session())
    signature = signed_url.split("X-Amz-Signature=")[1].split("&")[0]
    ws = FakeWs(fail=OSError(f"server rejected WebSocket connection: HTTP 403 ({signed_url})"))
    code = client.main(["--arn", ARN], connect=make_connect(ws), session=fake_session())
    output = "".join(capsys.readouterr())
    assert code == 1
    assert "HTTP 403" in output
    assert "X-Amz-Signature=***" in output
    assert signature not in output
    assert "AKIAFAKEFAKEFAKE" not in output  # access key id travels in X-Amz-Credential


def test_main_connection_error_exits_1_without_secret(capsys: pytest.CaptureFixture[str]) -> None:
    ws = FakeWs(fail=OSError("403 Forbidden"))
    code = client.main(["--arn", ARN], connect=make_connect(ws), session=fake_session())
    captured = capsys.readouterr()
    assert code == 1
    assert "403 Forbidden" in captured.out + captured.err
    assert FAKE_SECRET not in captured.out + captured.err
