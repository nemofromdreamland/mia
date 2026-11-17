import { MiaMark, type MiaState } from "@/components/MiaMark";
import { InlineNotice } from "@/components/InlineNotice";
import { Button } from "@/components/ui/button";
import type { VoiceStatus } from "@/voice/useVoice";
import { MicButton } from "./MicButton";

type VoiceBarProps = {
  status: VoiceStatus;
  muted: boolean;
  onToggleMute: () => void;
  onTextFallback: () => void;
  onRetry: () => void;
};

const STATUS: Record<VoiceStatus, { mark: MiaState; text: string }> = {
  mic: { mark: "idle", text: "Permita o acesso ao microfone para começar." },
  denied: { mark: "idle", text: "" },
  connecting: { mark: "thinking", text: "Conectando…" },
  speaking: { mark: "speaking", text: "MIA está falando. Você pode interromper falando por cima." },
  listening: { mark: "listening", text: "Sua vez. Pode falar." },
  interrupted: { mark: "listening", text: "Pode continuar." },
  thinking: { mark: "thinking", text: "MIA está pensando…" },
  failed: { mark: "idle", text: "" },
  ended: { mark: "idle", text: "" },
};

/** Design section 8: replaces the AnswerComposer in voice mode (96 px bar). */
export function VoiceBar({ status, muted, onToggleMute, onTextFallback, onRetry }: VoiceBarProps) {
  if (status === "denied") {
    return (
      <InlineNotice variant="danger">
        <p>
          O microfone está bloqueado. Libere o acesso nas configurações do navegador ou continue por texto.
        </p>
        <div className="mt-2 flex gap-4">
          <Button variant="link" size="sm" className="h-auto p-0" onClick={onTextFallback}>
            Continuar em texto
          </Button>
          <Button variant="link" size="sm" className="h-auto p-0" onClick={onRetry}>
            Tentar de novo
          </Button>
        </div>
      </InlineNotice>
    );
  }
  if (status === "failed") {
    return (
      <InlineNotice variant="neutral" action={{ label: "Continuar em texto", onClick: onTextFallback }}>
        Não foi possível reconectar. Continue por texto a partir da última pergunta.
      </InlineNotice>
    );
  }
  const live = status !== "mic" && status !== "connecting" && status !== "ended";
  const showMuted = muted && live && status !== "speaking";
  const { mark, text } = showMuted ? { mark: "idle" as const, text: "Microfone silenciado." } : STATUS[status];
  return (
    <div
      data-testid="voice-bar"
      className="flex flex-col items-center gap-3 md:h-[96px] md:flex-row md:justify-between"
    >
      <MiaMark state={mark} size={96} className="md:hidden" />
      <div className="flex w-full items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <MiaMark state={mark} size={64} className="hidden md:block" />
          <p role="status" className="text-body">
            {text}
          </p>
        </div>
        <MicButton muted={muted} disabled={!live} onToggle={onToggleMute} />
      </div>
    </div>
  );
}
