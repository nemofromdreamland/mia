import { useEffect, useState } from "react";
import { MiaMark } from "@/components/MiaMark";
import { Button } from "@/components/ui/button";
import { formatClock } from "@/lib/format";
import { elapsedSeconds, WARNING_AT_SECONDS } from "@/lib/interview";
import { personaColumn } from "@/lib/labels";
import type { Persona } from "@/lib/types";
import { cn } from "@/lib/utils";
import { SpeakerLabel } from "./SpeakerLabel";

type InterviewHeaderProps = {
  persona: Persona;
  jobTitle: string | null;
  questions: number;
  startedAt: string | null;
  onEnd: () => void;
  endDisabled?: boolean;
};

function useNow(): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  return now;
}

/** Design section 5.12: 56 px, fixed on top; clock warns from 40:00 on. */
export function InterviewHeader({ persona, jobTitle, questions, startedAt, onEnd, endDisabled }: InterviewHeaderProps) {
  const now = useNow();
  const seconds = startedAt ? elapsedSeconds(startedAt, now) : 0;
  const warning = seconds >= WARNING_AT_SECONDS;
  const clock = formatClock(seconds);
  const suffix = warning ? " · faltam 5 min" : "";
  return (
    <header className="sticky top-0 z-10 flex h-14 shrink-0 items-center justify-between gap-4 border-b border-border bg-background px-4 md:px-6">
      <div className="min-w-0">
        <div className="hidden md:block">
          <SpeakerLabel speaker="mia" persona={persona} />
        </div>
        <p className="flex items-center gap-2 md:hidden">
          <MiaMark size={20} />
          <span className="label text-mia">{`MIA · ${personaColumn(persona)}`}</span>
        </p>
        {jobTitle && <p className="hidden truncate text-small text-muted-foreground md:block">{jobTitle}</p>}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <span
          aria-hidden="true"
          className={cn("font-mono text-small tabular-nums", warning ? "text-warning" : "text-muted-foreground")}
        >
          <span className="hidden md:inline">{`Pergunta ${questions} · ${clock}${suffix}`}</span>
          <span className="md:hidden">{`P${questions} · ${clock}`}</span>
        </span>
        <span className="sr-only" aria-live="polite">
          {warning ? "Faltam 5 minutos." : ""}
        </span>
        <Button variant="ghost" data-testid="end-interview" aria-disabled={endDisabled} onClick={() => !endDisabled && onEnd()}>
          Encerrar
        </Button>
      </div>
    </header>
  );
}
