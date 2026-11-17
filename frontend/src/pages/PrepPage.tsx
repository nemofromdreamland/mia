import { useState } from "react";
import { useNavigate, useParams } from "react-router";
import { Clock, Headphones, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { AppHeader } from "@/components/AppHeader";
import { EvidenceQuote } from "@/components/EvidenceQuote";
import { FitScore } from "@/components/FitScore";
import { SessionNotFound } from "@/components/FullPageState";
import { InlineNotice } from "@/components/InlineNotice";
import { KeywordChip } from "@/components/KeywordChip";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useSessionView } from "@/hooks/useSessionView";
import { ApiError, apiRequest } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { interviewName } from "@/lib/labels";
import type { Evidence, PublicTurn, SessionView } from "@/lib/types";

/** Design section 6.4: who the visitor plays and the simulated recruiter's screening. */
export function PrepPage() {
  useDocumentTitle("Preparo");
  const { id = "" } = useParams();
  const { view, reload } = useSessionView(id, ["ready"]);

  if (view.state === "not_found") return <SessionNotFound />;
  return (
    <>
      <AppHeader role="candidate" />
      <main className="mx-auto flex max-w-[760px] flex-col gap-12 px-4 py-12 md:px-6">
        {view.state === "loading" && <PrepSkeleton />}
        {view.state === "error" && (
          <InlineNotice variant="danger" action={{ label: "Tentar de novo", onClick: reload }}>
            {errorMessage(view.error, "session_screen").text}
          </InlineNotice>
        )}
        {view.state === "ready" && <Screening id={id} view={view.view} reload={reload} />}
      </main>
    </>
  );
}

function PrepSkeleton() {
  return (
    <div data-testid="prep-skeleton" className="flex flex-col gap-4" aria-hidden="true">
      <Skeleton className="h-3 w-48 rounded-md" />
      <Skeleton className="h-10 w-3/4 rounded-md" />
      <Skeleton className="h-3 w-2/3 rounded-md" />
      <Skeleton className="mt-8 h-20 w-full rounded-md" />
      <Skeleton className="mt-8 h-12 w-40 rounded-md" />
      <Skeleton className="h-3 w-full rounded-md" />
      <Skeleton className="h-3 w-full rounded-md" />
    </div>
  );
}

type ScreeningProps = { id: string; view: SessionView; reload: () => Promise<void> };

function Screening({ id, view, reload }: ScreeningProps) {
  const navigate = useNavigate();
  const [starting, setStarting] = useState(false);
  const { session, screening } = view;
  const caseInfo = view.case;
  if (!screening) return null;

  async function start() {
    setStarting(true);
    try {
      await apiRequest<PublicTurn>("POST", `/sessions/${id}/start`);
      navigate(`/sessao/${id}/entrevista`);
    } catch (err) {
      setStarting(false);
      if (!(err instanceof ApiError)) return;
      toast(errorMessage(err, "session_screen").text);
      if (err.code === "invalid_state") await reload();
    }
  }

  return (
    <>
      <section className="flex flex-col gap-3">
        <p className="label text-muted-foreground">Triagem · visão do recrutador</p>
        <h1 className="text-h1">{screening.job_title}</h1>
        <p className="text-small text-muted-foreground">
          {caseInfo && `${caseInfo.company} · `}
          {`${interviewName(session.persona)} com a MIA · `}
          {caseInfo && (
            <>
              <Clock className="mr-1 inline size-4 align-text-bottom" aria-hidden="true" />
              {`cerca de ${caseInfo.estimated_minutes} min (máximo 45) · `}
            </>
          )}
          {session.mode === "voice" ? "Voz" : "Texto"}
        </p>
      </section>

      {caseInfo && (
        <section className="flex flex-col gap-1 border-l-2 border-border-strong p-4">
          <h2 className="label font-mono text-muted-foreground">Você vai interpretar</h2>
          <p className="text-answer text-foreground-soft">{caseInfo.candidate_blurb}</p>
        </section>
      )}

      <section className="flex flex-col gap-3" aria-labelledby="fit-title">
        <h2 id="fit-title" className="label font-mono text-muted-foreground">
          Aderência à vaga
        </h2>
        <FitScore score={screening.fit_score} />
      </section>

      <div className="grid grid-cols-1 gap-12 md:grid-cols-2 md:gap-6">
        <EvidenceList title="Pontos fortes" items={screening.strengths} />
        <EvidenceList title="Pontos de atenção" items={screening.concerns} />
      </div>

      {screening.missing_keywords.length > 0 && (
        <section className="flex flex-col gap-3">
          <h2 className="text-h2">Palavras-chave da vaga que não aparecem no CV</h2>
          <div className="flex flex-wrap gap-2">
            {screening.missing_keywords.map((k) => (
              <KeywordChip key={k}>{k}</KeywordChip>
            ))}
          </div>
        </section>
      )}

      <section className="flex flex-col gap-3">
        <h2 id="competencies-title" className="text-h2">
          O que será avaliado
        </h2>
        <ol aria-labelledby="competencies-title" className="flex flex-col gap-2">
          {screening.competencies.map((c, i) => (
            <li key={c} className="flex gap-3 text-body">
              <span className="font-mono text-muted-foreground tabular-nums">{i + 1}</span>
              {c}
            </li>
          ))}
        </ol>
        <p className="text-small text-muted-foreground">As perguntas só aparecem durante a entrevista.</p>
      </section>

      <div className="flex flex-col gap-4">
        {session.mode === "voice" && (
          <InlineNotice variant="neutral">
            <span className="inline-flex items-center gap-2">
              <Headphones className="size-4" aria-hidden="true" />
              Use fone de ouvido para a MIA não ouvir a própria voz.
            </span>
          </InlineNotice>
        )}
        <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-between">
          <Button variant="outline" className="w-full sm:w-auto" onClick={() => navigate("/")}>
            Voltar
          </Button>
          <Button
            className="w-full sm:w-auto"
            data-testid="start-interview"
            aria-busy={starting}
            aria-disabled={starting}
            onClick={() => !starting && void start()}
          >
            {starting && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
            {starting ? "Iniciando…" : "Começar entrevista"}
          </Button>
        </div>
      </div>
    </>
  );
}

function EvidenceList({ title, items }: { title: string; items: Evidence[] }) {
  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-h2">{title}</h2>
      {items.map((item) => (
        <div key={item.point} className="flex flex-col gap-2">
          <h3 className="text-h3">{item.point}</h3>
          <EvidenceQuote label="DO CV DO CASO" quote={item.cv_quote} />
        </div>
      ))}
    </section>
  );
}
