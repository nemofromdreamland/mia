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


def tool_use(content: str = '{"answer": "x"}', name: str = "submit_answer") -> list[dict]:
    return [
        {"contentStart": {"role": "TOOL", "type": "TOOL"}},
        {"toolUse": {"toolName": name, "toolUseId": "t1", "content": content}},
        {"contentEnd": {"type": "TOOL", "stopReason": "TOOL_USE"}},
    ]


def run(session: VoiceSession) -> list:
    async def go() -> list:
        await session.start()
        events = [e async for e in session.events()]
        await session.close()
        return events

    return asyncio.run(go())


def make(incoming: list[dict], brain: FakeBrain | None = None, tmp_path=None) -> VoiceSession:
    ticks = iter(range(100))
    return VoiceSession(
        FakeStream(incoming),
        brain or FakeBrain(),
        CONFIG,
        session_id="s1",
        clock=lambda: next(ticks) * 0.25,
        runs_dir=tmp_path,
    )


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
    assert tool["name"] == "submit_answer"


def test_system_prompt_carries_opening_line(tmp_path) -> None:
    session = make([], tmp_path=tmp_path)
    run(session)
    texts = [
        e["event"]["textInput"]["content"] for e in session.stream.sent if "textInput" in e["event"]
    ]
    assert "<abertura>Olá, eu sou a MIA. Conte sobre você.</abertura>" in texts[0]
    assert "feminino" in texts[0]


def test_tool_call_uses_candidate_transcript_and_returns_say(tmp_path) -> None:
    brain = FakeBrain()
    session = make(user_says("Eu fiz um projeto.") + tool_use(), brain, tmp_path)
    events = run(session)
    assert brain.answers == ["Eu fiz um projeto."]
    result = [e for e in session.stream.sent if "toolResult" in e["event"]][0]
    assert json.loads(result["event"]["toolResult"]["content"]) == {"say": "Próxima pergunta."}
    types = [e.type for e in events]
    assert types == ["state", "transcript", "turn.saved", "state"]
    assert events[1].payload == {"role": "candidate", "text": "Eu fiz um projeto.", "final": True}


def test_tool_falls_back_to_tool_argument_without_transcript(tmp_path) -> None:
    brain = FakeBrain()
    run(make(tool_use('{"answer": "só no argumento"}'), brain, tmp_path))
    assert brain.answers == ["só no argumento"]


def test_unknown_tool_is_refused_without_answer(tmp_path) -> None:
    brain = FakeBrain()
    session = make(user_says("oi") + tool_use(name="drop_table"), brain, tmp_path)
    run(session)
    assert brain.answers == []
    result = [e for e in session.stream.sent if "toolResult" in e["event"]][0]
    assert "error" in json.loads(result["event"]["toolResult"]["content"])


def test_service_error_becomes_error_event(tmp_path) -> None:
    brain = FakeBrain(error=ServiceError("session_limit", "Limite."))
    events = run(make(user_says("oi") + tool_use(), brain, tmp_path))
    assert events[-1].type == "error"
    assert events[-1].payload["code"] == "session_limit"


def test_audio_interruption_and_speculative_text(tmp_path) -> None:
    audio = base64.b64encode(b"\x00\x01").decode()
    incoming = [
        {
            "contentStart": {
                "role": "ASSISTANT",
                "additionalModelFields": '{"generationStage":"SPECULATIVE"}',
            }
        },
        {"textOutput": {"content": "Olá"}},
        {"audioOutput": {"content": audio}},
        {
            "contentStart": {
                "role": "ASSISTANT",
                "additionalModelFields": '{"generationStage":"FINAL"}',
            }
        },
        {"textOutput": {"content": "Olá"}},
        {"textOutput": {"content": '{ "interrupted" : true }'}},
        {"usageEvent": {"totalInputTokens": 10, "totalOutputTokens": 20}},
    ]
    session = make(incoming, tmp_path=tmp_path)
    events = run(session)
    assert [e.type for e in events] == [
        "state",
        "transcript",
        "audio.output",
        "transcript",
        "interrupted",
    ]
    assert events[1].payload["final"] is False
    assert events[3].payload["final"] is True
    assert events[2].payload == {"data": audio}
    assert session.first_audio_ms is not None
    assert (session.input_tokens, session.output_tokens) == (10, 20)


def test_ended_interview_emits_session_ended_after_farewell_audio(tmp_path) -> None:
    incoming = (
        user_says("tchau")
        + tool_use()
        + [
            {"contentStart": {"role": "ASSISTANT", "type": "AUDIO"}},
            {"contentEnd": {"type": "AUDIO", "stopReason": "END_TURN"}},
            {"textOutput": {"content": "nunca lido"}},
        ]
    )
    events = run(make(incoming, FakeBrain(ended=True), tmp_path))
    assert events[-1].type == "session.ended"
    assert events[-1].payload == {"status": "scoring"}


def test_run_record_has_masked_transcript_and_no_audio(tmp_path) -> None:
    audio = base64.b64encode(b"\x07" * 64).decode()
    incoming = user_says("meu email é ana@exemplo.com") + [{"audioOutput": {"content": audio}}]
    run(make(incoming, tmp_path=tmp_path))
    files = list(tmp_path.glob("*.jsonl"))
    line = files[0].read_text(encoding="utf-8")
    record = json.loads(line)
    assert record["prompt_name"] == "voice_interviewer"
    assert record["provider"] == "bedrock"
    assert "ana@exemplo.com" not in line
    assert audio not in line
    assert record["params"]["first_audio_ms"] is not None


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
