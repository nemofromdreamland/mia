import { forwardRef, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import type { Persona } from "@/lib/types";
import { SpeakerLabel } from "./SpeakerLabel";

export type TurnVariant = "mia" | "candidate" | "candidate-sending" | "candidate-failed";

type TranscriptTurnProps = {
  variant: TurnVariant;
  persona: Persona;
  text: string;
  onRetry?: () => void;
  followUp?: boolean;
  /** Replaces the plain answer text (the Report highlights quotes with <mark>). */
  children?: ReactNode;
};

/** Design section 5.9: speech aligned left, no bubble, no background. */
export const TranscriptTurn = forwardRef<HTMLDivElement, TranscriptTurnProps>(function TranscriptTurn(
  { variant, persona, text, onRetry, followUp, children },
  ref,
) {
  if (variant === "mia") {
    return (
      <div ref={ref} className="flex scroll-mt-4 flex-col gap-2">
        <SpeakerLabel speaker="mia" persona={persona} followUp={followUp} />
        <p className="fala text-foreground">{text}</p>
      </div>
    );
  }
  return (
    <div ref={ref} className="flex flex-col gap-2">
      <SpeakerLabel speaker="candidate" persona={persona} />
      <p className="whitespace-pre-wrap text-answer text-foreground-soft">{children ?? text}</p>
      {variant === "candidate-sending" && <p className="text-small text-muted-foreground">Enviando…</p>}
      {variant === "candidate-failed" && (
        <p className="flex items-center gap-2 text-small text-danger">
          Não enviada.
          <Button variant="link" size="sm" className="h-auto p-0" onClick={onRetry}>
            Tentar de novo
          </Button>
        </p>
      )}
    </div>
  );
});
