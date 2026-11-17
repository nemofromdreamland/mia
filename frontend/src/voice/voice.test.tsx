import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { VoiceBar } from "@/components/interview/VoiceBar";
import { mockApi } from "@/test/api";
import { makeView } from "@/test/data";
import { renderInterview } from "@/test/interview";
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

describe("VoiceBar (design section 8)", () => {
  const noop = () => {};
  const bar = (status: Parameters<typeof VoiceBar>[0]["status"], muted = false, onToggleMute = noop) =>
    render(
      <VoiceBar status={status} muted={muted} onToggleMute={onToggleMute} onTextFallback={noop} onRetry={noop} />,
    );

  it.each([
    ["mic", "Permita o acesso ao microfone para começar."],
    ["connecting", "Conectando…"],
    ["speaking", "MIA está falando. Você pode interromper falando por cima."],
    ["listening", "Sua vez. Pode falar."],
    ["interrupted", "Pode continuar."],
    ["thinking", "MIA está pensando…"],
  ] as const)("%s shows the design status text", (status, text) => {
    bar(status);
    expect(screen.getByRole("status")).toHaveTextContent(text);
  });

  it("mic button is unavailable while connecting", () => {
    bar("connecting");
    const button = screen.getByRole("button", { name: "Microfone indisponível" });
    expect(button).toHaveAttribute("aria-disabled", "true");
  });

  it("toggles mute with aria-pressed and the muted status", async () => {
    const toggle = vi.fn();
    const { rerender } = bar("listening", false, toggle);
    await userEvent.click(screen.getByRole("button", { name: "Silenciar microfone" }));
    expect(toggle).toHaveBeenCalled();
    rerender(<VoiceBar status="listening" muted onToggleMute={toggle} onTextFallback={noop} onRetry={noop} />);
    expect(screen.getByRole("button", { name: "Ativar microfone" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("status")).toHaveTextContent("Microfone silenciado.");
  });

  it("denied mic offers text and retry", () => {
    bar("denied");
    expect(screen.getByRole("alert")).toHaveTextContent("O microfone está bloqueado.");
    expect(screen.getByRole("button", { name: "Continuar em texto" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Tentar de novo" })).toBeInTheDocument();
  });

  it("failed connection offers continuing by text", () => {
    bar("failed");
    expect(screen.getByRole("note")).toHaveTextContent("Não foi possível reconectar.");
  });
});

describe("InterviewPage in voice mode", () => {
  beforeEach(() => sessionStorage.clear());

  it("replaces the composer with the VoiceBar and shows the denied notice", async () => {
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { getUserMedia: vi.fn().mockRejectedValue(new Error("NotAllowed")) },
    });
    const view = makeView(
      { turns: [], screening: null },
      { status: "in_progress", mode: "voice", started_at: new Date().toISOString() },
    );
    const { calls } = mockApi({ "GET /sessions/s1": view });
    renderInterview();
    expect(await screen.findByText(/O microfone está bloqueado/)).toBeInTheDocument();
    expect(screen.queryByTestId("answer-input")).not.toBeInTheDocument();
    expect(calls.some((c) => c.path.includes("voice-url"))).toBe(false);
  });

  it("uses the text composer after the tab chose text", async () => {
    sessionStorage.setItem("mia:voice-fallback:s1", "1");
    const view = makeView(
      { turns: [], screening: null },
      { status: "in_progress", mode: "voice", started_at: new Date().toISOString() },
    );
    mockApi({ "GET /sessions/s1": view });
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
