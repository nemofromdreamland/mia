import { useState } from "react";
import { ChevronDown, ChevronUp, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiError, apiRequest } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import type { ExamplesView } from "@/lib/types";

type AnswerExamplesProps = {
  sessionId: string;
  /** Text mode only: copies the example into the answer field. */
  onUse?: (text: string) => void;
};

/** Spec 5.6: closed by default; opens a strong and a weak answer for the current question. */
export function AnswerExamples({ sessionId, onUse }: AnswerExamplesProps) {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<ExamplesView | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function toggle() {
    if (open) {
      setOpen(false);
      return;
    }
    setOpen(true);
    setLoading(true);
    setError(null);
    try {
      setData(await apiRequest<ExamplesView>("GET", `/sessions/${sessionId}/examples`));
    } catch (err) {
      const e = err instanceof ApiError ? err : new ApiError("internal", true, null);
      setError(e.code === "not_found" ? "Sem exemplos para esta pergunta." : errorMessage(e, "interview").text);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <Button
        variant="link"
        size="sm"
        className="h-auto self-start p-0"
        aria-expanded={open}
        onClick={() => void toggle()}
        data-testid="examples-toggle"
      >
        {open ? <ChevronUp aria-hidden="true" /> : <ChevronDown aria-hidden="true" />}
        {open ? "Esconder exemplos" : "Ver exemplos"}
      </Button>
      {open && (
        <div className="flex max-h-[40dvh] flex-col gap-3 overflow-y-auto" data-testid="examples-panel">
          {loading && <Loader2 className="size-4 animate-spin text-muted-foreground" aria-label="Carregando" />}
          {error && <p className="text-small text-muted-foreground">{error}</p>}
          {data && (
            <>
              <Example title="Resposta forte" text={data.strong} onUse={onUse} testId="example-strong" />
              <Example title="Resposta fraca" text={data.weak} onUse={onUse} testId="example-weak" />
            </>
          )}
        </div>
      )}
    </div>
  );
}

function Example({
  title,
  text,
  onUse,
  testId,
}: {
  title: string;
  text: string;
  onUse?: (text: string) => void;
  testId: string;
}) {
  return (
    <section className="flex flex-col gap-1 border-l-2 border-border-strong pl-3" data-testid={testId}>
      <h3 className="label text-muted-foreground">{title}</h3>
      <p className="text-small text-foreground-soft">{text}</p>
      {onUse && (
        <Button variant="link" size="sm" className="h-auto self-start p-0" onClick={() => onUse(text)}>
          Usar este exemplo
        </Button>
      )}
    </section>
  );
}
