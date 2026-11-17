import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, apiRequest } from "@/lib/api";
import { bytesToBase64, chunkBytes } from "./pcm";
import { Player } from "./playback";
import { Recorder, playRecording } from "./recorder";

/** Connection / MIA state (Design section 8, adapted to recorded answers in spec 5.6). */
export type VoiceStatus = "connecting" | "speaking" | "listening" | "thinking" | "failed" | "ended";
/** The visitor's recording, like an audio message: nothing is sent before "Enviar". */
export type RecordState = "idle" | "recording" | "recorded" | "playing" | "denied";

export type LiveLine = {
  id: number;
  role: "interviewer" | "candidate";
  text: string;
  final: boolean;
  /** Candidate answers are shown as an audio bubble (the local recording), like WhatsApp. */
  audio?: Int16Array;
};

type ServerEvent = { type: string; payload?: Record<string, unknown> };

const RECORD_TICK_MS = 250;

export type UseVoice = {
  status: VoiceStatus;
  record: RecordState;
  recordedSeconds: number;
  notice: string | null;
  lines: LiveLine[];
  /** Grows on every turn.saved: the interviewer's next line is on its way. */
  turnsSaved: number;
  error: ApiError | null;
  startRecording: () => void;
  stopRecording: () => void;
  play: () => void;
  discard: () => void;
  send: () => void;
  /** Sends session.end over the socket; false when not connected (use REST /end). */
  end: () => boolean;
};

export const NOT_UNDERSTOOD = "Não entendi o áudio. Grave de novo.";

/** /ws -> PCM 24 kHz -> speakers; the visitor's recording -> /ws only on send(). */
export function useVoice(sessionId: string, enabled: boolean, onEnded: () => void): UseVoice {
  const [status, setStatus] = useState<VoiceStatus>("connecting");
  const [record, setRecord] = useState<RecordState>("idle");
  const [recordedSeconds, setRecordedSeconds] = useState(0);
  const [notice, setNotice] = useState<string | null>(null);
  const [lines, setLines] = useState<LiveLine[]>([]);
  const [turnsSaved, setTurnsSaved] = useState(0);
  const nextIdRef = useRef(0);
  const [error, setError] = useState<ApiError | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const recorderRef = useRef<Recorder | null>(null);
  const recordingRef = useRef<Int16Array | null>(null);
  const stopPlaybackRef = useRef<(() => void) | null>(null);
  const tickRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined);
  const endingRef = useRef(false);
  const onEndedRef = useRef(onEnded);
  onEndedRef.current = onEnded;

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    let player: Player | null = null;
    let ws: WebSocket | null = null;
    endingRef.current = false;

    const onLine = (role: LiveLine["role"], text: string, final: boolean) => {
      setLines((list) => {
        const last = list[list.length - 1];
        if (last && last.role === role && !last.final) {
          return [...list.slice(0, -1), { ...last, text, final }];
        }
        if (final && last && last.role === role && last.final && last.text === text) return list;
        return [...list, { id: nextIdRef.current++, role, text, final }];
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
          setStatus("speaking");
          break;
        case "transcript":
          // The candidate's own answer is already on screen as an audio bubble.
          if (p.role !== "candidate") onLine("interviewer", String(p.text ?? ""), Boolean(p.final));
          break;
        case "turn.saved":
          setTurnsSaved((n) => n + 1);
          break;
        case "state":
          // The voice did not come: the line is shown as text and it is the visitor's turn.
          if (p.voice_fallback) setStatus("listening");
          break;
        case "session.ended":
          endingRef.current = true;
          setStatus("ended");
          onEndedRef.current();
          break;
        case "error": {
          const code = String(p.code ?? "internal") as ApiError["code"];
          if (code === "invalid_input") {
            setNotice(NOT_UNDERSTOOD);
            setStatus("listening");
          } else {
            setError(new ApiError(code, Boolean(p.retryable), null));
          }
          break;
        }
      }
    };

    async function run() {
      try {
        const { url } = await apiRequest<{ url: string; expires_in: number }>(
          "POST",
          `/sessions/${sessionId}/voice-url`,
        );
        if (cancelled) return;
        player = new Player();
        player.onIdle = () => setStatus((s) => (s === "speaking" ? "listening" : s));
        await player.resume();
        ws = new WebSocket(url);
        wsRef.current = ws;
        ws.onopen = () => ws?.send(JSON.stringify({ type: "session.start", payload: { session_id: sessionId } }));
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
      wsRef.current = null;
      if (ws) {
        ws.onclose = null;
        ws.close();
      }
      player?.close();
      recorderRef.current?.release();
      stopPlaybackRef.current?.();
      clearInterval(tickRef.current);
    };
  }, [sessionId, enabled]);

  const startRecording = useCallback(() => {
    setNotice(null);
    stopPlaybackRef.current?.();
    const recorder = new Recorder();
    recorderRef.current = recorder;
    recorder
      .start()
      .then(() => {
        setRecord("recording");
        setRecordedSeconds(0);
        const started = Date.now();
        clearInterval(tickRef.current);
        tickRef.current = setInterval(
          () => setRecordedSeconds(Math.floor((Date.now() - started) / 1000)),
          RECORD_TICK_MS,
        );
      })
      .catch(() => {
        recorder.release();
        setRecord("denied");
      });
  }, []);

  const stopRecording = useCallback(() => {
    clearInterval(tickRef.current);
    const pcm = recorderRef.current?.stop() ?? new Int16Array();
    recorderRef.current = null;
    recordingRef.current = pcm;
    setRecordedSeconds(Math.round(pcm.length / 16_000));
    setRecord("recorded");
  }, []);

  const play = useCallback(() => {
    const pcm = recordingRef.current;
    if (!pcm) return;
    stopPlaybackRef.current?.();
    setRecord("playing");
    stopPlaybackRef.current = playRecording(pcm, () => setRecord("recorded"));
  }, []);

  const discard = useCallback(() => {
    stopPlaybackRef.current?.();
    recordingRef.current = null;
    setRecordedSeconds(0);
    setRecord("idle");
  }, []);

  const send = useCallback(() => {
    const pcm = recordingRef.current;
    const ws = wsRef.current;
    if (!pcm || ws?.readyState !== WebSocket.OPEN) return;
    stopPlaybackRef.current?.();
    for (const chunk of chunkBytes(new Uint8Array(pcm.buffer, pcm.byteOffset, pcm.byteLength))) {
      ws.send(JSON.stringify({ type: "audio.chunk", payload: { data: bytesToBase64(chunk) } }));
    }
    ws.send(JSON.stringify({ type: "answer.submit", payload: {} }));
    setLines((list) => [...list, { id: nextIdRef.current++, role: "candidate", text: "", final: true, audio: pcm }]);
    recordingRef.current = null;
    setRecord("idle");
    setStatus("thinking");
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

  return {
    status,
    record,
    recordedSeconds,
    notice,
    lines,
    turnsSaved,
    error,
    startRecording,
    stopRecording,
    play,
    discard,
    send,
    end,
  };
}
