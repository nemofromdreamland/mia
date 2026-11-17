"""Offline tests for `/ws` (spec 5, step 2): fake voice session, no AWS."""

import asyncio
import base64

import pytest
from fakes_service import CASE_ID, VISITOR_A, VISITOR_B, make_deps
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from mia.api import create_app
from mia.api.ws import VISITOR_HEADER
from mia.llm import load_voice_config
from mia.schemas import ServerEvent
from mia.service import create_session

CONFIG = load_voice_config(env={})


class FakeVoice:
    """Duck-typed VoiceSession: one opening transcript, then waits for browser events."""

    def __init__(self) -> None:
        self.config = CONFIG
        self.audio: list[bytes] = []
        self.started = self.closed = self.ended_called = False
        self.queue: asyncio.Queue[ServerEvent | None] = asyncio.Queue()

    async def start(self) -> None:
        self.started = True
        await self.queue.put(
            ServerEvent(
                type="transcript", payload={"role": "interviewer", "text": "Olá", "final": True}
            )
        )

    async def events(self):
        while (event := await self.queue.get()) is not None:
            yield event

    async def send_audio(self, pcm: bytes) -> None:
        self.audio.append(pcm)

    async def end_interview(self) -> None:
        self.ended_called = True

    async def close(self) -> None:
        self.closed = True


def setup(mode: str = "voice"):
    deps = make_deps()
    sid = create_session(deps, VISITOR_A, CASE_ID, mode).session_id
    app = create_app(deps)
    voice = FakeVoice()

    async def factory(d, visitor, session_id):
        assert (visitor, session_id) == (VISITOR_A, sid)
        return voice

    app.state.voice_factory = factory
    return TestClient(app), sid, voice


def connect(client: TestClient, visitor: str | None = VISITOR_A):
    headers = {VISITOR_HEADER: visitor} if visitor else {}
    return client.websocket_connect("/ws", headers=headers)


def chunk(data: bytes) -> dict:
    return {"type": "audio.chunk", "payload": {"data": base64.b64encode(data).decode()}}


def start(sid: str) -> dict:
    return {"type": "session.start", "payload": {"session_id": sid}}


def expect_close(ws, code: int) -> dict:
    error = ws.receive_json()
    with pytest.raises(WebSocketDisconnect) as exc:
        ws.receive_json()
    assert exc.value.code == code
    return error


def test_production_app_exposes_ws() -> None:
    from mia.api.main import build_app

    with TestClient(build_app({"MIA_STORAGE": "memory"})).websocket_connect("/ws") as ws:
        assert expect_close(ws, 1008)["type"] == "error"


@pytest.mark.parametrize("visitor", [None, "abc"])
def test_missing_or_bad_visitor_header_closes_1008(visitor) -> None:
    client, sid, voice = setup()
    with connect(client, visitor) as ws:
        assert expect_close(ws, 1008)["payload"]["code"] == "invalid_input"
    assert not voice.started


def test_plain_x_visitor_id_header_is_not_accepted() -> None:
    client, sid, _ = setup()
    with client.websocket_connect("/ws", headers={"X-Visitor-Id": VISITOR_A}) as ws:
        assert expect_close(ws, 1008)["payload"]["code"] == "invalid_input"


def test_first_event_must_be_session_start() -> None:
    client, sid, voice = setup()
    with connect(client) as ws:
        ws.send_json(chunk(b"\x00\x00"))
        assert expect_close(ws, 1008)["payload"]["code"] == "invalid_input"
    assert not voice.started


def test_other_visitors_session_is_not_found() -> None:
    client, sid, voice = setup()
    with connect(client, VISITOR_B) as ws:
        ws.send_json(start(sid))
        assert expect_close(ws, 1008)["payload"]["code"] == "not_found"
    assert not voice.started


def test_text_session_is_invalid_state() -> None:
    client, sid, _ = setup(mode="text")
    with connect(client) as ws:
        ws.send_json(start(sid))
        assert expect_close(ws, 1008)["payload"]["code"] == "invalid_state"


def test_happy_path_audio_mute_and_end() -> None:
    client, sid, voice = setup()
    with connect(client) as ws:
        ws.send_json(start(sid))
        assert ws.receive_json()["type"] == "transcript"
        ws.send_json(chunk(b"\x01\x02"))
        ws.send_json({"type": "audio.mute", "payload": {"muted": True}})
        ws.send_json(chunk(b"\x03\x04"))
        ws.send_json({"type": "session.end", "payload": {}})
        assert ws.receive_json() == {"type": "session.ended", "payload": {"status": "scoring"}}
    assert voice.audio == [b"\x01\x02", b"\x00\x00"]  # muted audio becomes silence
    assert voice.ended_called and voice.closed


@pytest.mark.parametrize(
    "frame",
    [
        chunk(b"\x00" * 5000),  # too big
        chunk(b"\x00"),  # odd length
        {"type": "audio.chunk", "payload": {"data": "@@@"}},  # not base64
        {"type": "hack", "payload": {}},
        {"type": "audio.mute", "payload": {"muted": True, "visitor_id": VISITOR_B}},
    ],
)
def test_invalid_frames_get_error_and_are_not_forwarded(frame) -> None:
    client, sid, voice = setup()
    with connect(client) as ws:
        ws.send_json(start(sid))
        ws.receive_json()
        ws.send_json(frame)
        error = ws.receive_json()
        assert error["type"] == "error" and error["payload"]["code"] == "invalid_input"
        ws.send_json({"type": "session.end", "payload": {}})
        ws.receive_json()
    assert voice.audio == []


def test_disconnect_closes_voice_without_ending_interview() -> None:
    client, sid, voice = setup()
    with connect(client) as ws:
        ws.send_json(start(sid))
        ws.receive_json()
    for _ in range(50):
        if voice.closed:
            break
        asyncio.run(asyncio.sleep(0.01))
    assert voice.closed and not voice.ended_called


def test_factory_failure_is_internal_without_details() -> None:
    client, sid, _ = setup()

    async def broken(d, visitor, session_id):
        raise RuntimeError("arn:aws:secret-detail")

    client.app.state.voice_factory = broken
    with connect(client) as ws:
        ws.send_json(start(sid))
        error = expect_close(ws, 1011)
    assert error["payload"]["code"] == "internal"
    assert "arn" not in str(error)
