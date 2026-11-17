"""Offline tests for the Sonic voice session (spec 5, step 1): no AWS, no audio device."""

import asyncio
import base64
import json

import pytest
from fakes_service import CASE_ID, VISITOR_A, VISITOR_B, make_deps

from mia.llm import load_voice_config
from mia.quotas import InMemoryMetaStore, QuotaGate, global_key
from mia.service import ServiceError, authorize_voice, create_session, voice_state
from mia.voice.sonic import Opening, Reply, ServiceBrain, VoiceSession

CONFIG = load_voice_config(env={})


class FakeStream:
    def __init__(self, incoming: list[dict]) -> None:
        self.sent: list[dict] = []
        self.incoming = list(incoming)
        self.closed = False

    async def send(self, event: dict) -> None:
        self.sent.append(event)

    async def receive(self) -> dict | None:
        return {"event": self.incoming.pop(0)} if self.incoming else None

    async def close(self) -> None:
        self.closed = True

    def names(self) -> list[str]:
        return [next(iter(e["event"])) for e in self.sent]


class FakeBrain:
    def __init__(self, ended: bool = False, error: ServiceError | None = None) -> None:
        self.answers: list[str] = []
        self.ended = ended
        self.error = error
        self.closed = False

    def opening(self) -> Opening:
        return Opening(say="Olá, eu sou a MIA. Conte sobre você.", state={"question_no": 1})

    def answer(self, text: str) -> Reply:
        if self.error:
            raise self.error
        self.answers.append(text)
        return Reply(say="Próxima pergunta.", turn_no=1, ended=self.ended, state={"question_no": 2})

    def end(self) -> None:
        self.closed = True


def user_says(text: str) -> list[dict]:
    return [{"contentStart": {"role": "USER", "type": "TEXT"}}, {"textOutput": {"content": text}}]


def tool_use(name: str = "next_line") -> list[dict]:
    return [
        {"contentStart": {"role": "TOOL", "type": "TOOL"}},
        {"toolUse": {"toolName": name, "toolUseId": "t1", "content": "{}"}},
        {"contentEnd": {"type": "TOOL", "stopReason": "TOOL_USE"}},
    ]


def assistant_audio(data: bytes = b"\x00\x01") -> list[dict]:
    return [
        {"contentStart": {"role": "ASSISTANT", "type": "AUDIO"}},
        {"audioOutput": {"content": base64.b64encode(data).decode()}},
    ]


def run(session: VoiceSession) -> list:
    async def go() -> list:
        await session.start()
        events = [e async for e in session.events()]
        await session.close()
        return events

    return asyncio.run(go())


def make(incoming: list[dict], brain: FakeBrain | None = None, tmp_path=None) -> VoiceSession:
    ticks = iter(range(1000))
    return VoiceSession(
        FakeStream(incoming),
        brain or FakeBrain(),
        CONFIG,
        session_id="s1",
        clock=lambda: next(ticks) * 0.25,
        runs_dir=tmp_path,
    )


def tool_results(session: VoiceSession) -> list[dict]:
    return [
        json.loads(e["event"]["toolResult"]["content"])
        for e in session.stream.sent
        if "toolResult" in e["event"]
    ]


def user_texts(session: VoiceSession) -> list[str]:
    return [
        e["event"]["textInput"]["content"] for e in session.stream.sent if "textInput" in e["event"]
    ]


async def hear(session: VoiceSession, text: str) -> None:
    for event in user_says(text):
        await session._handle(event)


@pytest.fixture(autouse=True)
def fast_submit(monkeypatch) -> None:
    monkeypatch.setattr("mia.voice.sonic.TRAILING_SILENCE_S", 0.2)
    monkeypatch.setattr("mia.voice.sonic.QUIET_S", 0.05)
    monkeypatch.setattr("mia.voice.sonic.SUBMIT_TIMEOUT_S", 0.3)


def test_voice_config_defaults_to_carolina_and_env_overrides() -> None:
    assert CONFIG.voice_id == "carolina"
    assert CONFIG.model_id == "amazon.nova-2-sonic-v1:0"
    assert load_voice_config(env={"MIA_VOICE_ID": "tiffany"}).voice_id == "tiffany"


def test_start_and_close_follow_protocol_order(tmp_path) -> None:
    session = make([], tmp_path=tmp_path)
    run(session)
    names = session.stream.names()
    assert names[:2] == ["sessionStart", "promptStart"]
    assert names[-3:] == ["contentEnd", "promptEnd", "sessionEnd"]
    assert session.stream.closed
    prompt_start = session.stream.sent[1]["event"]["promptStart"]
    assert prompt_start["audioOutputConfiguration"]["voiceId"] == "carolina"
    tool = prompt_start["toolConfiguration"]["tools"][0]["toolSpec"]
    assert tool["name"] == "next_line"


def test_opening_is_read_through_next_line(tmp_path) -> None:
    session = make(tool_use(), tmp_path=tmp_path)
    run(session)
    system, trigger = user_texts(session)[:2]
    assert "feminino" in system and "next_line" in system
    assert trigger == "(resposta enviada)"
    assert tool_results(session) == [{"say": "Olá, eu sou a MIA. Conte sobre você."}]


def test_unknown_tool_or_unrequested_call_gets_empty_say(tmp_path) -> None:
    session = make(tool_use("drop_table") + tool_use(), tmp_path=tmp_path)
    run(session)
    assert tool_results(session) == [{"say": ""}, {"say": ""}]  # 2nd: opening already used


def test_submit_uses_transcript_saves_and_speaks_next_line(tmp_path) -> None:
    brain = FakeBrain()
    session = make([], brain, tmp_path)

    async def go() -> list:
        await session.start()
        await session.send_client_audio(b"\x01\x02")
        await hear(session, "Eu fiz um projeto.")
        await hear(session, " Com Python.")
        return await session.submit()

    events = asyncio.run(go())
    assert brain.answers == ["Eu fiz um projeto. Com Python."]
    assert [e.type for e in events] == ["turn.saved", "state"]
    assert user_texts(session)[-1] == "(resposta enviada)"
    assert session._next_say == "Próxima pergunta."


def test_submit_without_transcript_is_invalid_input_and_saves_nothing(tmp_path) -> None:
    brain = FakeBrain()
    session = make([], brain, tmp_path)

    async def go() -> list:
        await session.start()
        return await session.submit()

    events = asyncio.run(go())
    assert brain.answers == []
    assert events[0].type == "error"
    assert events[0].payload["code"] == "invalid_input"
    assert events[0].payload["message"] == "Não entendi o áudio. Grave de novo."


def test_submit_service_error_becomes_error_event(tmp_path) -> None:
    session = make([], FakeBrain(error=ServiceError("session_limit", "Limite.")), tmp_path)

    async def go() -> list:
        await session.start()
        await hear(session, "oi")
        return await session.submit()

    assert asyncio.run(go())[0].payload["code"] == "session_limit"


def test_sonic_output_is_dropped_until_the_code_asks(tmp_path) -> None:
    session = make([], tmp_path=tmp_path)

    async def go() -> tuple[list, list]:
        await session.start()
        await session.send_client_audio(b"\x01\x02")
        dropped: list = []
        for event in assistant_audio() + [{"textOutput": {"content": "comentário próprio"}}]:
            dropped += await session._handle(event)
        session._next_say = "Próxima."
        for event in tool_use():
            await session._handle(event)
        spoken: list = []
        for event in assistant_audio():
            spoken += await session._handle(event)
        return dropped, spoken

    dropped, spoken = asyncio.run(go())
    assert dropped == []
    assert [e.type for e in spoken] == ["audio.output"]


def test_marker_echo_and_interruptions_are_not_forwarded(tmp_path) -> None:
    incoming = user_says("(resposta enviada)") + [
        {"contentStart": {"role": "ASSISTANT"}},
        {"textOutput": {"content": '{ "interrupted" : true }'}},
    ]
    events = run(make(incoming, tmp_path=tmp_path))
    assert [e.type for e in events] == ["state"]


def test_speculative_and_final_interviewer_text(tmp_path) -> None:
    speculative = '{"generationStage":"SPECULATIVE"}'
    final = '{"generationStage":"FINAL"}'
    incoming = [
        {"contentStart": {"role": "ASSISTANT", "additionalModelFields": speculative}},
        {"textOutput": {"content": "Olá"}},
        {"contentStart": {"role": "ASSISTANT", "additionalModelFields": final}},
        {"textOutput": {"content": "Olá"}},
        {"usageEvent": {"totalInputTokens": 10, "totalOutputTokens": 20}},
        *assistant_audio(),
    ]
    session = make(incoming, tmp_path=tmp_path)
    events = run(session)
    assert [e.type for e in events] == ["state", "transcript", "transcript", "audio.output"]
    assert events[1].payload["final"] is False and events[2].payload["final"] is True
    assert session.first_audio_ms is not None
    assert (session.input_tokens, session.output_tokens) == (10, 20)


def test_ended_interview_emits_session_ended_after_farewell_audio(tmp_path) -> None:
    session = make([], FakeBrain(ended=True), tmp_path)

    async def go() -> list:
        await session.start()
        await hear(session, "tchau")
        await session.submit()
        out: list = []
        for event in [
            {"contentStart": {"role": "ASSISTANT", "type": "AUDIO"}},
            {"contentEnd": {"type": "AUDIO", "stopReason": "END_TURN"}},
        ]:
            out += await session._handle(event)
        return out

    events = asyncio.run(go())
    assert events[-1].type == "session.ended" and events[-1].payload == {"status": "scoring"}


def test_keepalive_sends_silence_until_closed(tmp_path) -> None:
    session = make([], tmp_path=tmp_path)

    async def go() -> None:
        task = asyncio.create_task(session.keepalive())
        await asyncio.sleep(0.35)
        await session.close()
        await asyncio.wait_for(task, 1)

    asyncio.run(go())
    silence = [e for e in session.stream.sent if "audioInput" in e["event"]]
    assert silence
    assert all(
        base64.b64decode(e["event"]["audioInput"]["content"]) == bytes(3200) for e in silence
    )


def test_run_record_has_masked_transcript_and_no_audio(tmp_path) -> None:
    audio = base64.b64encode(b"\x07" * 64).decode()
    incoming = user_says("meu email é ana@exemplo.com") + [{"audioOutput": {"content": audio}}]
    run(make(incoming, tmp_path=tmp_path))
    line = next(tmp_path.glob("*.jsonl")).read_text(encoding="utf-8")
    record = json.loads(line)
    assert record["prompt_name"] == "voice_interviewer" and record["prompt_version"] == 2
    assert "ana@exemplo.com" not in line
    assert audio not in line


def test_close_is_idempotent_and_survives_send_error(tmp_path) -> None:
    class Broken(FakeStream):
        async def send(self, event: dict) -> None:
            raise RuntimeError("boom")

    session = VoiceSession(Broken([]), FakeBrain(), CONFIG, runs_dir=tmp_path)

    async def go() -> None:
        await session.close()
        await session.close()

    asyncio.run(go())
    assert session.stream.closed
    assert session.error == "RuntimeError"


def test_send_audio_encodes_pcm_and_stops_after_close(tmp_path) -> None:
    session = make([], tmp_path=tmp_path)

    async def go() -> None:
        await session.send_audio(b"\x01\x02")
        await session.close()
        await session.send_audio(b"\x03\x04")

    asyncio.run(go())
    audio = [e for e in session.stream.sent if "audioInput" in e["event"]]
    assert len(audio) == 1
    assert audio[0]["event"]["audioInput"]["content"] == base64.b64encode(b"\x01\x02").decode()


def test_end_interview_calls_brain_once(tmp_path) -> None:
    brain = FakeBrain()
    session = make([], brain, tmp_path)
    asyncio.run(session.end_interview())
    assert brain.closed and session.ended


# ----- ServiceBrain + service helpers (real service, in-memory repo) -----


def voice_session(deps, visitor: str = VISITOR_A) -> str:
    return create_session(deps, visitor, CASE_ID, "voice").session_id


def test_service_brain_opening_starts_then_reconnects_with_same_line() -> None:
    deps = make_deps()
    sid = voice_session(deps)
    brain = ServiceBrain(deps, VISITOR_A, sid)
    first = brain.opening()
    assert deps.repo.get_session(VISITOR_A, sid).status == "in_progress"
    assert brain.opening().say == first.say
    assert first.state["question_no"] == 1


def test_service_brain_answer_saves_turn_and_returns_next_line() -> None:
    deps = make_deps(scorer=lambda q, a: None)
    sid = voice_session(deps)
    brain = ServiceBrain(deps, VISITOR_A, sid)
    brain.opening()
    reply = brain.answer("Trabalhei com Python.")
    turns = deps.repo.list_turns(VISITOR_A, sid)
    assert turns[reply.turn_no - 1].answer_text == "Trabalhei com Python."
    assert reply.say == turns[-1].interviewer_text
    assert reply.state["question_no"] == 2


def test_voice_state_and_authorize_voice() -> None:
    deps = make_deps()
    sid = voice_session(deps)
    authorize_voice(deps, VISITOR_A, sid)  # ready: allowed
    assert voice_state(deps, VISITOR_A, sid)["elapsed_s"] == 0
    with pytest.raises(ServiceError) as other:
        authorize_voice(deps, VISITOR_B, sid)
    assert other.value.code == "not_found"
    text_sid = create_session(deps, VISITOR_A, CASE_ID, "text").session_id
    with pytest.raises(ServiceError) as wrong_mode:
        authorize_voice(deps, VISITOR_A, text_sid)
    assert wrong_mode.value.code == "invalid_state"


def test_authorize_voice_respects_kill_switch_without_consuming_quota() -> None:
    store = InMemoryMetaStore()
    deps = make_deps()
    sid = voice_session(deps)
    paused = deps.model_copy(update={"gate": QuotaGate(store, clock=deps.clock)})
    authorize_voice(paused, VISITOR_A, sid)
    assert store.get_count(global_key(), deps.clock().date().isoformat()) == 0
    store.set_demo_open(False)
    with pytest.raises(ServiceError) as exc:
        authorize_voice(paused, VISITOR_A, sid)
    assert exc.value.code == "demo_paused"
