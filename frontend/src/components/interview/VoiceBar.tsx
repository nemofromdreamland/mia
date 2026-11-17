import { Mic, Play, Send, Square, Trash2 } from "lucide-react";
import { MiaMark, type MiaState } from "@/components/MiaMark";
import { InlineNotice } from "@/components/InlineNotice";
import { Button } from "@/components/ui/button";
import type { RecordState, VoiceStatus } from "@/voice/useVoice";

type VoiceBarProps = {
  status: VoiceStatus;
  record: RecordState;
  seconds: number;
  notice: string | null;
  onRecord: () => void;
  onStop: () => void;
  onPlay: () => void;
  onDiscard: () => void;
  onSend: () => void;
  onTextFallback: () => void;
};

const STATUS: Record<VoiceStatus, { mark: MiaState; text: string }> = {
  connecting: { mark: "thinking", text: "Conectando…" },
  speaking: { mark: "speaking", text: "MIA está falando." },
  listening: { mark: "listening", text: "Sua vez. Grave sua resposta." },
  thinking: { mark: "thinking", text: "MIA está pensando…" },
  failed: { mark: "idle", text: "" },
  ended: { mark: "idle", text: "" },
};

function clock(seconds: number): string {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

/** Spec 5.6: voice answers are recorded like an audio message (record, listen, delete, send). */
export function VoiceBar(props: VoiceBarProps) {
  const { status, record, notice, onTextFallback } = props;
  if (status === "failed") {
    return (
      <InlineNotice variant="neutral" action={{ label: "Continuar em texto", onClick: onTextFallback }}>
        Não foi possível reconectar. Continue por texto a partir da última pergunta.
      </InlineNotice>
    );
  }
  if (record === "denied") {
    return (
      <InlineNotice variant="danger">
        <p>O microfone está bloqueado. Libere o acesso nas configurações do navegador ou continue por texto.</p>
        <div className="mt-2 flex gap-4">
          <Button variant="link" size="sm" className="h-auto p-0" onClick={onTextFallback}>
            Continuar em texto
          </Button>
          <Button variant="link" size="sm" className="h-auto p-0" onClick={props.onRecord}>
            Tentar de novo
          </Button>
        </div>
      </InlineNotice>
    );
  }
  const recording = record === "recording";
  const { mark, text } = recording ? { mark: "listening" as const, text: "Gravando…" } : STATUS[status];
  return (
    <div data-testid="voice-bar" className="flex flex-col gap-3">
      {notice && <InlineNotice variant="warning">{notice}</InlineNotice>}
      <div className="flex min-h-[64px] flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <MiaMark state={mark} size={48} />
          <p role="status" className="text-body">
            {text}
          </p>
        </div>
        <RecordControls {...props} />
      </div>
    </div>
  );
}

function RecordControls({ status, record, seconds, onRecord, onStop, onPlay, onDiscard, onSend }: VoiceBarProps) {
  if (record === "recording") {
    return (
      <div className="flex items-center gap-3">
        <span className="font-mono tabular-nums text-danger" aria-live="off">
          ● {clock(seconds)}
        </span>
        <Button onClick={onStop} data-testid="record-stop">
          <Square aria-hidden="true" />
          Parar
        </Button>
      </div>
    );
  }
  if (record === "recorded" || record === "playing") {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono tabular-nums text-muted-foreground">{clock(seconds)}</span>
        <Button variant="outline" onClick={onPlay} disabled={record === "playing"} data-testid="record-play">
          <Play aria-hidden="true" />
          {record === "playing" ? "Tocando…" : "Ouvir"}
        </Button>
        <Button variant="outline" onClick={onDiscard} data-testid="record-discard">
          <Trash2 aria-hidden="true" />
          Apagar
        </Button>
        <Button onClick={onSend} disabled={status !== "listening"} data-testid="record-send">
          <Send aria-hidden="true" />
          Enviar
        </Button>
      </div>
    );
  }
  return (
    <Button onClick={onRecord} disabled={status !== "listening"} data-testid="record-start">
      <Mic aria-hidden="true" />
      Gravar resposta
    </Button>
  );
}
