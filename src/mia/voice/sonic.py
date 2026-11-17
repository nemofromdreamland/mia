"""Voice interview over Nova 2 Sonic (specs 5 and 5.6).

Sonic is only ears and mouth. The visitor records an answer and clicks Enviar: the code waits for
Sonic's transcript, runs the same service flow as text mode (`Brain`), saves the turn and decides
the next line. Sonic then fetches that ready line with the argument-less `next_line` tool and
reads it (tool results are read word for word; plain text gets paraphrased). Sonic output the
code did not ask for is dropped. Audio stays in memory; only masked text is saved.
"""

import asyncio
import base64
import json
import time
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel

from mia import service
from mia.llm import DEFAULT_RUNS_DIR, SonicStream, record_voice_run
from mia.pii import mask_text
from mia.prompts import load_prompt, render
from mia.schemas import ServerEvent, VoiceConfig
from mia.service import ServiceDeps, ServiceError

PROMPT_NAME = "voice_interviewer"
PROMPT_VERSION = 2
TOOL_NAME = "next_line"
SUBMITTED_TEXT = "(resposta enviada)"
# After the recording is sent: trailing silence lets Sonic finalize the transcript; then we
# wait until no new candidate text arrives for QUIET_S (at most SUBMIT_TIMEOUT_S).
TRAILING_SILENCE_S = 1.5
QUIET_S = 1.2
SUBMIT_TIMEOUT_S = 8.0
SILENCE_CHUNK = bytes(3200)  # 100 ms of PCM 16 kHz mono
KEEPALIVE_S = 0.1
# The browser sends a whole recording at once; Sonic gets it at ~5x real time (validated on the
# real model: 4096-byte chunk = 128 ms of audio).
CLIENT_CHUNK_PAUSE_S = 0.025
# Sonic sometimes ignores the "(resposta enviada)" marker (seen in production): resend it, and
# if it still does not fetch the line, show the line as text so the interview never stalls.
SPOKEN_WAIT_S = 4.0
SPEAK_RETRIES = 2
EMPTY_MESSAGE = "Não entendi o áudio. Grave de novo."
ENDED_PAYLOAD = {"status": "scoring"}


class Reply(BaseModel):
    """What the brain decided after an answer: the next line to speak."""

    say: str
    turn_no: int  # the answered turn, now saved
    ended: bool = False
    state: dict[str, Any] = {}


class Opening(BaseModel):
    say: str
    state: dict[str, Any] = {}


class Brain(Protocol):
    """Deterministic side of the interview (sync: it calls the service)."""

    def opening(self) -> Opening: ...

    def answer(self, text: str) -> Reply: ...

    def end(self) -> None: ...


class ServiceBrain:
    """Brain backed by mia.service: same rules, limits and persistence as text mode."""

    def __init__(self, deps: ServiceDeps, visitor_id: str, session_id: str) -> None:
        self.deps = deps
        self.visitor_id = visitor_id
        self.session_id = session_id

    def opening(self) -> Opening:
        session = self.deps.repo.get_session(self.visitor_id, self.session_id)
        if session.status == "ready":
            turn = service.start_interview(self.deps, self.visitor_id, self.session_id)
            return Opening(say=turn.interviewer_text, state=self._state())
        turns = self.deps.repo.list_turns(self.visitor_id, self.session_id)
        return Opening(say=turns[-1].interviewer_text, state=self._state())  # reconnect

    def answer(self, text: str) -> Reply:
        result = service.send_answer(self.deps, self.visitor_id, self.session_id, text)
        turns = self.deps.repo.list_turns(self.visitor_id, self.session_id)
        last = turns[-1]
        if result.ended:
            return Reply(say=last.interviewer_text, turn_no=last.turn_no - 1, ended=True)
        return Reply(say=last.interviewer_text, turn_no=last.turn_no - 1, state=self._state())

    def end(self) -> None:
        service.end_interview(self.deps, self.visitor_id, self.session_id)

    def _state(self) -> dict[str, Any]:
        return service.voice_state(self.deps, self.visitor_id, self.session_id)


def _event(name: str, body: dict[str, Any]) -> dict[str, Any]:
    return {"event": {name: body}}


def _stage(content_start: dict[str, Any]) -> str | None:
    extra = content_start.get("additionalModelFields")
    if not extra:
        return None
    try:
        stage = json.loads(extra).get("generationStage")
    except (ValueError, AttributeError):
        return None
    return stage if isinstance(stage, str) else None


class VoiceSession:
    """One Sonic conversation bridged to MIA's browser protocol (ServerEvent)."""

    def __init__(
        self,
        stream: SonicStream,
        brain: Brain,
        config: VoiceConfig,
        *,
        session_id: str | None = None,
        clock: Any = time.monotonic,
        runs_dir: Path = DEFAULT_RUNS_DIR,
    ) -> None:
        self.runs_dir = runs_dir
        self.stream = stream
        self.brain = brain
        self.config = config
        self.session_id = session_id
        self.clock = clock
        self.prompt_name = str(uuid.uuid4())
        self.audio_name = str(uuid.uuid4())
        self.started_at: float | None = None
        self.first_audio_ms: int | None = None
        self.transcript: list[dict[str, str]] = []
        self.input_tokens = 0
        self.output_tokens = 0
        self.error: str | None = None
        self.ended = False
        self._closed = False
        self._role: str | None = None
        self._stage: str | None = None
        self._pending: list[str] = []  # candidate's final text since the last submit
        self._heard_at = 0.0  # monotonic time of the last candidate text
        self._muted_output = False  # drop Sonic output the code did not ask for
        self._client_audio_at = 0.0
        self._next_say: str | None = None
        self._spoken = asyncio.Event()
        self._tool: dict[str, Any] | None = None
        self._ending = False
        self._initial_state: dict[str, Any] = {}

    # ----- outgoing (MIA -> Sonic) -----

    async def start(self) -> None:
        """Open the conversation: sessionStart, promptStart (voice + tool), system prompt,
        the opening trigger and a continuous audio input content."""
        opening = await asyncio.to_thread(self.brain.opening)
        self.started_at = self.clock()
        prompt = render(load_prompt(PROMPT_NAME, PROMPT_VERSION), {})
        send = self.stream.send
        await send(
            _event(
                "sessionStart",
                {"inferenceConfiguration": {"maxTokens": 1024, "topP": 0.9, "temperature": 0.3}},
            )
        )
        await send(_event("promptStart", self._prompt_start()))
        await self._send_text("SYSTEM", prompt.system, interactive=False)
        self._next_say = opening.say  # read through next_line, like every other line
        await self._send_text("USER", prompt.user.strip(), interactive=True)
        await send(_event("contentStart", self._audio_start()))
        self._initial_state = opening.state

    def _prompt_start(self) -> dict[str, Any]:
        return {
            "promptName": self.prompt_name,
            "textOutputConfiguration": {"mediaType": "text/plain"},
            "audioOutputConfiguration": {
                "mediaType": "audio/lpcm",
                "sampleRateHertz": self.config.output_sample_rate,
                "sampleSizeBits": 16,
                "channelCount": 1,
                "voiceId": self.config.voice_id,
                "encoding": "base64",
                "audioType": "SPEECH",
            },
            "toolUseOutputConfiguration": {"mediaType": "application/json"},
            "toolConfiguration": {
                "tools": [
                    {
                        "toolSpec": {
                            "name": TOOL_NAME,
                            "description": "Devolve a próxima fala da entrevistadora no campo say.",
                            "inputSchema": {
                                "json": json.dumps({"type": "object", "properties": {}})
                            },
                        }
                    }
                ]
            },
        }

    def _audio_start(self) -> dict[str, Any]:
        return {
            "promptName": self.prompt_name,
            "contentName": self.audio_name,
            "type": "AUDIO",
            "interactive": True,
            "role": "USER",
            "audioInputConfiguration": {
                "mediaType": "audio/lpcm",
                "sampleRateHertz": self.config.input_sample_rate,
                "sampleSizeBits": 16,
                "channelCount": 1,
                "audioType": "SPEECH",
                "encoding": "base64",
            },
        }

    async def _send_text(self, role: str, text: str, *, interactive: bool) -> None:
        name = str(uuid.uuid4())
        await self.stream.send(
            _event(
                "contentStart",
                {
                    "promptName": self.prompt_name,
                    "contentName": name,
                    "type": "TEXT",
                    "interactive": interactive,
                    "role": role,
                    "textInputConfiguration": {"mediaType": "text/plain"},
                },
            )
        )
        await self.stream.send(
            _event(
                "textInput", {"promptName": self.prompt_name, "contentName": name, "content": text}
            )
        )
        await self.stream.send(
            _event("contentEnd", {"promptName": self.prompt_name, "contentName": name})
        )

    async def send_audio(self, pcm: bytes) -> None:
        if self._closed:
            return
        await self.stream.send(
            _event(
                "audioInput",
                {
                    "promptName": self.prompt_name,
                    "contentName": self.audio_name,
                    "content": base64.b64encode(pcm).decode("ascii"),
                },
            )
        )

    async def speak(self, text: str) -> None:
        """Make Sonic read `text`: it fetches it with next_line (see the module docstring)."""
        self._next_say = text
        self._spoken.clear()
        await self._send_text("USER", SUBMITTED_TEXT, interactive=True)

    async def _speak_reliably(self, text: str) -> bool:
        """speak() + resend the marker while Sonic has not fetched the line. False = gave up."""
        await self.speak(text)
        for attempt in range(SPEAK_RETRIES + 1):
            try:
                await asyncio.wait_for(self._spoken.wait(), SPOKEN_WAIT_S)
                return True
            except TimeoutError:
                if attempt < SPEAK_RETRIES:
                    await self._send_text("USER", SUBMITTED_TEXT, interactive=True)
        self._next_say = None
        return False

    async def _send_tool_result(self, tool_use_id: str, result: dict[str, Any]) -> None:
        name = str(uuid.uuid4())
        await self.stream.send(
            _event(
                "contentStart",
                {
                    "promptName": self.prompt_name,
                    "contentName": name,
                    "interactive": False,
                    "type": "TOOL",
                    "role": "TOOL",
                    "toolResultInputConfiguration": {
                        "toolUseId": tool_use_id,
                        "type": "TEXT",
                        "textInputConfiguration": {"mediaType": "text/plain"},
                    },
                },
            )
        )
        await self.stream.send(
            _event(
                "toolResult",
                {
                    "promptName": self.prompt_name,
                    "contentName": name,
                    "content": json.dumps(result, ensure_ascii=False),
                },
            )
        )
        await self.stream.send(
            _event("contentEnd", {"promptName": self.prompt_name, "contentName": name})
        )

    async def _on_tool(self, tool: dict[str, Any]) -> None:
        say, self._next_say = self._next_say, None
        if tool.get("toolName") != TOOL_NAME or say is None:
            await self._send_tool_result(tool.get("toolUseId", ""), {"say": ""})
            return
        self._muted_output = False  # from here on, Sonic speaks the line the code chose
        self._spoken.set()
        await self._send_tool_result(tool.get("toolUseId", ""), {"say": say})

    async def send_client_audio(self, pcm: bytes) -> None:
        """Audio from the visitor's recording; Sonic's own replies are dropped until we speak."""
        self._client_audio_at = time.monotonic()
        self._muted_output = True
        await self.send_audio(pcm)
        await asyncio.sleep(CLIENT_CHUNK_PAUSE_S)

    async def keepalive(self) -> None:
        """Sonic expects a continuous audio stream: send silence while the visitor is not
        sending a recording (the microphone is closed by default)."""
        while not self._closed:
            if time.monotonic() - self._client_audio_at > KEEPALIVE_S * 2:
                await self.send_audio(SILENCE_CHUNK)
            await asyncio.sleep(KEEPALIVE_S)

    async def submit(self) -> list[ServerEvent]:
        """The visitor clicked Enviar: wait for the transcript, then run the text-mode flow and
        speak the next line. The code decides; Sonic never chooses when an answer ends."""
        for _ in range(int(TRAILING_SILENCE_S / 0.1)):
            await self.send_audio(SILENCE_CHUNK)
        started = time.monotonic()
        while time.monotonic() - started < SUBMIT_TIMEOUT_S:
            heard = self._pending and time.monotonic() - self._heard_at >= QUIET_S
            if heard:
                break
            await asyncio.sleep(0.1)
        text = " ".join(t.strip() for t in self._pending).strip()
        self._pending = []
        if not text:
            return [_error(ServiceError("invalid_input", EMPTY_MESSAGE))]
        try:
            reply = await asyncio.to_thread(self.brain.answer, text)
        except ServiceError as exc:
            return [_error(exc)]
        spoken = await self._speak_reliably(reply.say)
        events = [ServerEvent(type="turn.saved", payload={"turn_no": reply.turn_no})]
        if not spoken:  # fallback: the line goes to the screen; the visitor can answer
            self.transcript.append({"role": "interviewer", "text": reply.say})
            events.append(_transcript("interviewer", reply.say, final=True))
            events.append(ServerEvent(type="state", payload={"voice_fallback": True}))
            if reply.ended:
                self.ended = True
                events.append(ServerEvent(type="session.ended", payload=ENDED_PAYLOAD))
                return events
        if reply.ended:
            self._ending = True
        elif reply.state:
            events.append(ServerEvent(type="state", payload=reply.state))
        return events

    # ----- incoming (Sonic -> MIA) -----

    async def events(self) -> AsyncIterator[ServerEvent]:
        """Translate Sonic output into ServerEvents until the stream or the interview ends."""
        if self._initial_state:
            yield ServerEvent(type="state", payload=self._initial_state)
        while not self.ended:
            raw = await self.stream.receive()
            if raw is None:
                return
            for event in await self._handle(raw.get("event", {})):
                yield event

    async def _handle(self, event: dict[str, Any]) -> list[ServerEvent]:
        if "contentStart" in event:
            start = event["contentStart"]
            self._role = start.get("role")
            self._stage = _stage(start)
            return []
        if "textOutput" in event:
            return self._on_text(event["textOutput"].get("content", ""))
        if "audioOutput" in event:
            if self._muted_output:
                return []
            if self.first_audio_ms is None and self.started_at is not None:
                self.first_audio_ms = int((self.clock() - self.started_at) * 1000)
            return [
                ServerEvent(type="audio.output", payload={"data": event["audioOutput"]["content"]})
            ]
        if "toolUse" in event:
            self._tool = event["toolUse"]
            return []
        if "contentEnd" in event:
            return await self._on_content_end(event["contentEnd"])
        if "usageEvent" in event:
            usage = event["usageEvent"]
            self.input_tokens = int(usage.get("totalInputTokens", self.input_tokens))
            self.output_tokens = int(usage.get("totalOutputTokens", self.output_tokens))
        return []  # completionStart/End and other bookkeeping events

    def _on_text(self, text: str) -> list[ServerEvent]:
        if self._role == "ASSISTANT" and '"interrupted"' in text:
            return []  # no voice barge-in in 5.6: the visitor records instead
        if self._role == "USER":
            if text.strip() == SUBMITTED_TEXT:
                return []  # our own marker echoed back
            self._pending.append(text)
            self._heard_at = time.monotonic()
            self.transcript.append({"role": "candidate", "text": mask_text(text)})
            return [_transcript("candidate", text, final=True)]
        if self._role == "ASSISTANT":
            if self._muted_output:
                return []
            final = self._stage != "SPECULATIVE"
            if final:
                self.transcript.append({"role": "interviewer", "text": text})
            return [_transcript("interviewer", text, final=final)]
        return []

    async def _on_content_end(self, end: dict[str, Any]) -> list[ServerEvent]:
        if end.get("type") == "TOOL" and self._tool is not None:
            tool, self._tool = self._tool, None
            await self._on_tool(tool)
            return []
        if self._ending and end.get("type") == "AUDIO" and end.get("stopReason") == "END_TURN":
            self.ended = True
            return [ServerEvent(type="session.ended", payload=ENDED_PAYLOAD)]
        return []

    # ----- shutdown -----

    async def end_interview(self) -> None:
        """Visitor clicked Encerrar: close through the existing service flow."""
        if not self._ending:
            await asyncio.to_thread(self.brain.end)
        self.ended = True

    async def close(self) -> None:
        """Close Sonic in protocol order (audio contentEnd, promptEnd, sessionEnd) and write
        the run record. Safe to call twice and after errors."""
        if self._closed:
            return
        self._closed = True
        try:
            name = self.prompt_name
            await self.stream.send(
                _event("contentEnd", {"promptName": name, "contentName": self.audio_name})
            )
            await self.stream.send(_event("promptEnd", {"promptName": name}))
            await self.stream.send(_event("sessionEnd", {}))
        except Exception as exc:  # noqa: BLE001 - closing must not raise
            self.error = self.error or type(exc).__name__
        finally:
            await self.stream.close()
            self._record()

    def _record(self) -> None:
        duration = 0 if self.started_at is None else int((self.clock() - self.started_at) * 1000)
        record_voice_run(
            config=self.config,
            prompt_name=PROMPT_NAME,
            prompt_version=PROMPT_VERSION,
            session_id=self.session_id,
            transcript=self.transcript,
            first_audio_ms=self.first_audio_ms,
            duration_ms=duration,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            error=self.error,
            runs_dir=self.runs_dir,
        )


def _transcript(role: str, text: str, *, final: bool) -> ServerEvent:
    return ServerEvent(type="transcript", payload={"role": role, "text": text, "final": final})


def _error(exc: ServiceError) -> ServerEvent:
    return ServerEvent(
        type="error",
        payload={"code": exc.code, "message": exc.message, "retryable": exc.retryable},
    )
