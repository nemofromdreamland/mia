import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, apiRequest } from "@/lib/api";
import { INPUT_RATE, bytesToBase64, chunkBytes, downsample, floatTo16 } from "./pcm";
import { Player } from "./playback";
import { workletUrl } from "./worklet";

/** Design section 8 states (reconnect is out of scope in spec 5: a drop goes to "failed"). */
export type VoiceStatus =
  | "mic"
  | "denied"
  | "connecting"
  | "speaking"
  | "listening"
  | "interrupted"
  | "thinking"
  | "failed"
  | "ended";

export type LiveLine = { id: number; role: "interviewer" | "candidate"; text: string; final: boolean };
export type VoiceState = { phase?: string; question_no?: number; elapsed_s?: number };

type ServerEvent = { type: string; payload?: Record<string, unknown> };

const INTERRUPTED_MS = 1500;

export type UseVoice = {
  status: VoiceStatus;
  muted: boolean;
  lines: LiveLine[];
  error: ApiError | null;
  toggleMute: () => void;
  /** Sends session.end over the socket; false when not connected (use REST /end). */
  end: () => boolean;
  retry: () => void;
};

/** Mic -> AudioWorklet -> PCM 16 kHz -> /ws; /ws -> PCM 24 kHz -> speakers. Nothing is stored. */
export function useVoice(sessionId: string, enabled: boolean, onEnded: () => void): UseVoice {
  const [status, setStatus] = useState<VoiceStatus>("mic");
  const [muted, setMuted] = useState(false);
  const [lines, setLines] = useState<LiveLine[]>([]);
  const [error, setError] = useState<ApiError | null>(null);
  const [attempt, setAttempt] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);
  const mutedRef = useRef(false);
  const endingRef = useRef(false);
  const onEndedRef = useRef(onEnded);
  onEndedRef.current = onEnded;

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    let stream: MediaStream | null = null;
    let captureCtx: AudioContext | null = null;
    let player: Player | null = null;
    let ws: WebSocket | null = null;
    let nextId = 0;
    let interruptTimer: ReturnType<typeof setTimeout> | undefined;
    endingRef.current = false;
    setStatus("mic");

    const send = (event: object) => {
      if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify(event));
    };

    const onLine = (role: LiveLine["role"], text: string, final: boolean) => {
      setLines((list) => {
        const last = list[list.length - 1];
        // A partial line is replaced by the next partial/final of the same speaker.
        if (last && last.role === role && !last.final) {
          return [...list.slice(0, -1), { ...last, text, final }];
        }
        if (final && last && last.role === role && last.final && last.text === text) return list;
        return [...list, { id: nextId++, role, text, final }];
      });
    };

    const onMessage = (raw: string) => {
      let event: ServerEvent;
      try {
        event = JSON.parse(raw) as ServerEvent;
      } catch {
        return;
      }
      const p = event.payload ?? {};
      switch (event.type) {
        case "audio.output":
          player?.play(String(p.data ?? ""));
          setStatus((s) => (s === "interrupted" ? s : "speaking"));
          break;
        case "transcript":
          onLine(p.role === "candidate" ? "candidate" : "interviewer", String(p.text ?? ""), Boolean(p.final));
          if (p.role === "candidate" && p.final) setStatus("thinking");
          break;
        case "interrupted":
          player?.stop();
          setStatus("interrupted");
          clearTimeout(interruptTimer);
          interruptTimer = setTimeout(() => setStatus("listening"), INTERRUPTED_MS);
          break;
        case "session.ended":
          endingRef.current = true;
          setStatus("ended");
          onEndedRef.current();
          break;
        case "error": {
          const code = String(p.code ?? "internal") as ApiError["code"];
          setError(new ApiError(code, Boolean(p.retryable), null));
          break;
        }
      }
    };

    async function run() {
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
        });
      } catch {
        if (!cancelled) setStatus("denied");
        return;
      }
      if (cancelled) return;
      setStatus("connecting");
      try {
        const { url } = await apiRequest<{ url: string; expires_in: number }>(
          "POST",
          `/sessions/${sessionId}/voice-url`,
        );
        if (cancelled) return;
        player = new Player();
        player.onIdle = () => setStatus((s) => (s === "speaking" ? "listening" : s));
        await player.resume();
        captureCtx = new AudioContext();
        const moduleUrl = workletUrl();
        await captureCtx.audioWorklet.addModule(moduleUrl);
        URL.revokeObjectURL(moduleUrl);
        const node = new AudioWorkletNode(captureCtx, "mia-capture");
        captureCtx.createMediaStreamSource(stream).connect(node);
        const rate = captureCtx.sampleRate;
        node.port.onmessage = (e: MessageEvent<Float32Array>) => {
          if (ws?.readyState !== WebSocket.OPEN) return;
          const pcm = floatTo16(downsample(e.data, rate, INPUT_RATE));
          const bytes = new Uint8Array(pcm.buffer);
          for (const chunk of chunkBytes(bytes)) {
            send({ type: "audio.chunk", payload: { data: bytesToBase64(chunk) } });
          }
        };
        ws = new WebSocket(url);
        wsRef.current = ws;
        ws.onopen = () => {
          send({ type: "session.start", payload: { session_id: sessionId } });
          if (mutedRef.current) send({ type: "audio.mute", payload: { muted: true } });
        };
        ws.onmessage = (e) => onMessage(String(e.data));
        ws.onclose = () => {
          if (!cancelled && !endingRef.current) setStatus("failed");
        };
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof ApiError ? err : new ApiError("internal", true, null));
        setStatus("failed");
      }
    }

    void run();
    return () => {
      cancelled = true;
      clearTimeout(interruptTimer);
      wsRef.current = null;
      if (ws) {
        ws.onclose = null;
        ws.close();
      }
      stream?.getTracks().forEach((t) => t.stop());
      void captureCtx?.close().catch(() => {});
      player?.close();
    };
  }, [sessionId, enabled, attempt]);

  const toggleMute = useCallback(() => {
    const next = !mutedRef.current;
    mutedRef.current = next;
    setMuted(next);
    const ws = wsRef.current;
    if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "audio.mute", payload: { muted: next } }));
  }, []);

  const end = useCallback(() => {
    const ws = wsRef.current;
    endingRef.current = true;
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "session.end", payload: {} }));
      setStatus("thinking");
      return true;
    }
    return false;
  }, []);

  const retry = useCallback(() => {
    setError(null);
    setAttempt((n) => n + 1);
  }, []);

  return { status, muted, lines, error, toggleMute, end, retry };
}
