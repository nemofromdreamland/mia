"""`/ws`: MIA's voice protocol (Backend Schema, "WebSocket") bridged to a Sonic VoiceSession.

The browser never sees Sonic events. Identity comes only from the AgentCore custom header
that the proxy put inside the SigV4-signed URL (spec 5); the event body never carries it.
Audio is only forwarded in memory.
"""

import asyncio
import base64
import binascii
import contextlib
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import TypeAdapter, ValidationError

from mia.api.visitor import parse_visitor_id
from mia.llm import load_voice_config, open_sonic_stream
from mia.schemas import (
    AudioChunkEvent,
    AudioMuteEvent,
    ClientEvent,
    ServerEvent,
    SessionEndEvent,
    SessionStartEvent,
    VoiceConfig,
)
from mia.service import ServiceDeps, ServiceError, authorize_voice
from mia.voice.sonic import ENDED_PAYLOAD, ServiceBrain, VoiceSession

logger = logging.getLogger(__name__)

VISITOR_HEADER = "x-amzn-bedrock-agentcore-runtime-custom-x-visitor-id"
START_TIMEOUT_S = 5.0
POLICY_VIOLATION = 1008
INTERNAL_ERROR = 1011

VoiceFactory = Callable[[ServiceDeps, str, str], Awaitable[VoiceSession]]
_client_event: TypeAdapter[Any] = TypeAdapter(ClientEvent)

router = APIRouter()


async def sonic_voice_factory(deps: ServiceDeps, visitor_id: str, session_id: str) -> VoiceSession:
    """Production factory: real Sonic stream + the service-backed brain."""
    config = load_voice_config()
    stream = await open_sonic_stream(config)
    brain = ServiceBrain(deps, visitor_id, session_id)
    return VoiceSession(stream, brain, config, session_id=session_id)


def _error(code: str, message: str, retryable: bool = False) -> dict[str, Any]:
    return ServerEvent(
        type="error", payload={"code": code, "message": message, "retryable": retryable}
    ).model_dump()


def parse_event(text: str) -> Any:
    """Validate one client frame; raises ValueError/ValidationError when it is not allowed."""
    return _client_event.validate_json(text)


def decode_chunk(event: AudioChunkEvent, config: VoiceConfig) -> bytes:
    """PCM 16-bit mono in base64: even length, at most `max_chunk_bytes` decoded."""
    try:
        pcm = base64.b64decode(event.payload.data, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("audio.chunk inválido") from exc
    if not pcm or len(pcm) % 2 or len(pcm) > config.max_chunk_bytes:
        raise ValueError("audio.chunk inválido")
    return pcm


async def _close(ws: WebSocket, code: int, error: dict[str, Any] | None = None) -> None:
    with contextlib.suppress(Exception):
        if error is not None:
            await ws.send_json(error)
        await ws.close(code)


async def _wait_start(ws: WebSocket) -> SessionStartEvent:
    text = await asyncio.wait_for(ws.receive_text(), START_TIMEOUT_S)
    event = parse_event(text)
    if not isinstance(event, SessionStartEvent):
        raise ValueError("o primeiro evento deve ser session.start")
    return event


@router.websocket("/ws")
async def voice_ws(ws: WebSocket) -> None:
    await ws.accept()
    try:
        visitor_id = parse_visitor_id(ws.headers.get(VISITOR_HEADER))
    except ServiceError:
        await _close(ws, POLICY_VIOLATION, _error("invalid_input", "Visitante inválido."))
        return
    deps: ServiceDeps = ws.app.state.deps
    try:
        start = await _wait_start(ws)
        session_id = start.payload.session_id
        await asyncio.to_thread(authorize_voice, deps, visitor_id, session_id)
    except ServiceError as exc:
        await _close(ws, POLICY_VIOLATION, _error(exc.code, exc.message, exc.retryable))
        return
    except (TimeoutError, ValueError, ValidationError, WebSocketDisconnect):
        await _close(ws, POLICY_VIOLATION, _error("invalid_input", "Comece com session.start."))
        return
    factory: VoiceFactory = getattr(ws.app.state, "voice_factory", sonic_voice_factory)
    voice: VoiceSession | None = None
    try:
        voice = await factory(deps, visitor_id, session_id)
        await voice.start()
        await _bridge(ws, voice)
        await _close(ws, 1000)
    except ServiceError as exc:
        await _close(ws, POLICY_VIOLATION, _error(exc.code, exc.message, exc.retryable))
    except Exception:  # noqa: BLE001 - never leak provider details to the browser
        logger.exception("voice session failed")
        await _close(ws, INTERNAL_ERROR, _error("internal", "Erro na voz. Tente de novo.", True))
    finally:
        if voice is not None:
            await voice.close()


async def _bridge(ws: WebSocket, voice: VoiceSession) -> None:
    """Run browser->Sonic and Sonic->browser until one side finishes."""
    outgoing = asyncio.create_task(_pump_out(ws, voice))
    incoming = asyncio.create_task(_pump_in(ws, voice))
    done, pending = await asyncio.wait({outgoing, incoming}, return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task
    for task in done:
        exc = task.exception()
        if exc is not None and not isinstance(exc, WebSocketDisconnect):
            raise exc


async def _pump_out(ws: WebSocket, voice: VoiceSession) -> None:
    async for event in voice.events():
        await ws.send_json(event.model_dump())
        if event.type == "session.ended":
            return


async def _pump_in(ws: WebSocket, voice: VoiceSession) -> None:
    muted = False
    while True:
        text = await ws.receive_text()
        try:
            event = parse_event(text)
            if isinstance(event, AudioChunkEvent):
                pcm = decode_chunk(event, voice.config)
                # Muted: keep the stream alive with silence, never the visitor's audio.
                await voice.send_audio(bytes(len(pcm)) if muted else pcm)
            elif isinstance(event, AudioMuteEvent):
                muted = event.payload.muted
            elif isinstance(event, SessionEndEvent):
                await voice.end_interview()
                await ws.send_json(
                    ServerEvent(type="session.ended", payload=ENDED_PAYLOAD).model_dump()
                )
                return
            else:
                raise ValueError("session.start repetido")
        except (ValueError, ValidationError):
            await ws.send_json(_error("invalid_input", "Evento inválido."))
        except ServiceError as exc:
            await ws.send_json(_error(exc.code, exc.message, exc.retryable))
