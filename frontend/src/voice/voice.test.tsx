import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { VoiceBar } from "@/components/interview/VoiceBar";
import { mockApi } from "@/test/api";
import { makeView } from "@/test/data";
import { renderInterview } from "@/test/interview";
import { NOT_UNDERSTOOD } from "./useVoice";
import { MAX_CHUNK_BYTES, base64ToInt16, bytesToBase64, chunkBytes, downsample, floatTo16 } from "./pcm";

describe("pcm", () => {
  it("downsamples 48 kHz to 16 kHz by averaging", () => {
    const out = downsample(new Float32Array([0, 0.3, 0.6, 1, 1, 1]), 48_000, 16_000);
    expect(Array.from(out).map((v) => Number(v.toFixed(2)))).toEqual([0.3, 1]);
  });

  it("clamps floats into int16 and round-trips through base64", () => {
    const pcm = floatTo16(new Float32Array([-2, 0, 2]));
    expect(Array.from(pcm)).toEqual([-32768, 0, 32767]);
    const back = base64ToInt16(bytesToBase64(new Uint8Array(pcm.buffer)));
    expect(Array.from(back)).toEqual([-32768, 0, 32767]);
  });

  it("splits audio into even chunks of at most 4096 bytes", () => {
    const chunks = chunkBytes(new Uint8Array(10_000));
    expect(chunks.map((c) => c.length)).toEqual([4096, 4096, 1808]);
    expect(chunks.every((c) => c.length <= MAX_CHUNK_BYTES && c.length % 2 === 0)).toBe(true);
  });
});

describe("VoiceBar (spec 5.6: recorded answers)", () => {
  const noop = () => {};
  type Props = Parameters<typeof VoiceBar>[0];
  const bar = (over: Partial<Props> = {}) => {
    const props: Props = {
      status: "listening",
      record: "idle",
      seconds: 0,
      notice: null,
      onRecord: vi.fn(),
      onStop: vi.fn(),
      onPlay: vi.fn(),
      onDiscard: vi.fn(),
      onSend: vi.fn(),
      onTextFallback: noop,
      ...over,
    };
    render(<VoiceBar {...props} />);
    return props;
  };

  it.each([
    ["connecting", "Conectando…"],
    ["speaking", "MIA está falando."],
    ["listening", "Sua vez. Grave sua resposta."],
    ["thinking", "MIA está pensando…"],
  ] as const)("%s shows its status", (status, text) => {
    bar({ status });
    expect(screen.getByRole("status")).toHaveTextContent(text);
  });

  it("starts with the microphone closed: only 'Gravar resposta', enabled on your turn", async () => {
    const props = bar();
    await userEvent.click(screen.getByTestId("record-start"));
    expect(props.onRecord).toHaveBeenCalled();
  });

  it.each(["speaking", "thinking", "connecting"] as const)("cannot record while %s", (status) => {
    bar({ status });
    expect(screen.getByTestId("record-start")).toBeDisabled();
  });

  it("recording shows the timer and Parar", async () => {
    const props = bar({ record: "recording", seconds: 72 });
    expect(screen.getByRole("status")).toHaveTextContent("Gravando…");
    expect(screen.getByText(/1:12/)).toBeInTheDocument();
    await userEvent.click(screen.getByTestId("record-stop"));
    expect(props.onStop).toHaveBeenCalled();
  });

  it("recorded answer can be heard, deleted or sent", async () => {
    const props = bar({ record: "recorded", seconds: 9 });
    await userEvent.click(screen.getByTestId("record-play"));
    await userEvent.click(screen.getByTestId("record-discard"));
    await userEvent.click(screen.getByTestId("record-send"));
    expect(props.onPlay).toHaveBeenCalled();
    expect(props.onDiscard).toHaveBeenCalled();
    expect(props.onSend).toHaveBeenCalled();
  });

  it("shows the not-understood notice", () => {
    bar({ notice: NOT_UNDERSTOOD });
    expect(screen.getByRole("alert")).toHaveTextContent("Não entendi o áudio. Grave de novo.");
  });

  it("denied mic offers text and retry", () => {
    bar({ record: "denied" });
    expect(screen.getByRole("alert")).toHaveTextContent("O microfone está bloqueado.");
    expect(screen.getByRole("button", { name: "Continuar em texto" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Tentar de novo" })).toBeInTheDocument();
  });

  it("failed connection offers continuing by text", () => {
    bar({ status: "failed" });
    expect(screen.getByRole("note")).toHaveTextContent("Não foi possível reconectar.");
  });
});

describe("InterviewPage in voice mode", () => {
  beforeEach(() => sessionStorage.clear());

  const voiceView = () =>
    makeView(
      { turns: [], screening: null },
      { status: "in_progress", mode: "voice", started_at: new Date().toISOString() },
    );

  it("never asks for the microphone on open, and shows the VoiceBar", async () => {
    const getUserMedia = vi.fn();
    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { getUserMedia } });
    mockApi({
      "GET /sessions/s1": voiceView(),
      "POST /sessions/s1/voice-url": () => new Promise<Response>(() => {}),
    });
    renderInterview();
    expect(await screen.findByTestId("voice-bar")).toBeInTheDocument();
    expect(screen.queryByTestId("answer-input")).not.toBeInTheDocument();
    expect(getUserMedia).not.toHaveBeenCalled();
  });

  it("uses the text composer after the tab chose text", async () => {
    sessionStorage.setItem("mia:voice-fallback:s1", "1");
    mockApi({ "GET /sessions/s1": voiceView() });
    renderInterview();
    await waitFor(() => expect(screen.getByTestId("answer-input")).toBeInTheDocument());
    expect(screen.queryByTestId("voice-bar")).not.toBeInTheDocument();
  });
});

describe("liveLines", () => {
  it("hides the re-spoken opening even when split, but keeps later lines", async () => {
    const { liveLines } = await import("./lines");
    const last = "Oi, tudo bem? Qual foi o maior desafio?";
    const lines = [
      { id: 0, role: "interviewer" as const, text: "Oi, tudo bem?", final: true },
      { id: 1, role: "interviewer" as const, text: " Qual foi o maior desafio?", final: true },
      { id: 2, role: "candidate" as const, text: "Foi a latência.", final: true },
      { id: 3, role: "interviewer" as const, text: "Qual foi o maior desafio?", final: true },
    ];
    expect(liveLines(lines, last).map((l) => l.id)).toEqual([2, 3]);
  });
});
