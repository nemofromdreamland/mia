import { useEffect, useRef } from "react";
import { useNavigate } from "react-router";
import { Loader2 } from "lucide-react";
import { InlineNotice } from "@/components/InlineNotice";
import { MiaMark } from "@/components/MiaMark";
import { Button } from "@/components/ui/button";

type EndPanelProps = {
  status: "scoring" | "completed";
  sessionId: string;
  pollError: boolean;
  onRetry: () => void;
};

/** Design sections 5.28 and 6.5: replaces the composer; never redirects by itself. */
export function EndPanel({ status, sessionId, pollError, onRetry }: EndPanelProps) {
  const navigate = useNavigate();
  const feedbackRef = useRef<HTMLButtonElement>(null);
  const ready = status === "completed";

  useEffect(() => {
    if (ready) feedbackRef.current?.focus();
  }, [ready]);

  return (
    <div className="flex flex-col items-center gap-4 rounded-lg bg-card p-6 text-center">
      <MiaMark size={48} state={ready ? "idle" : "thinking"} />
      <h2 className="text-h2">Entrevista encerrada</h2>
      <p className="text-body text-foreground-soft">
        {ready
          ? "Seu feedback está pronto."
          : "A MIA está avaliando suas respostas. Isso costuma levar menos de um minuto."}
      </p>
      <p className="sr-only" aria-live="polite">
        {ready ? "Seu feedback está pronto." : ""}
      </p>
      {pollError && !ready && (
        <InlineNotice variant="danger" className="w-full text-left" action={{ label: "Tentar de novo", onClick: onRetry }}>
          Não foi possível verificar a avaliação.
        </InlineNotice>
      )}
      <div className="flex w-full flex-col-reverse gap-3 sm:w-auto sm:flex-row">
        <Button variant="outline" onClick={() => navigate("/")}>
          Voltar ao início
        </Button>
        <Button
          ref={feedbackRef}
          data-testid="view-feedback"
          aria-disabled={!ready}
          aria-busy={!ready}
          onClick={() => ready && navigate(`/sessao/${sessionId}/relatorio`)}
        >
          {!ready && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
          {ready ? "Ver feedback" : "Avaliando…"}
        </Button>
      </div>
    </div>
  );
}
