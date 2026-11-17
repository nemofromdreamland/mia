import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { Check, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { AppHeader } from "@/components/AppHeader";
import { SessionNotFound } from "@/components/FullPageState";
import { InlineNotice } from "@/components/InlineNotice";
import { MiaMark } from "@/components/MiaMark";
import { AboveAverageNote } from "@/components/report/AboveAverageNote";
import { AnswerByAnswer } from "@/components/report/AnswerByAnswer";
import { CompetencyRow } from "@/components/report/CompetencyRow";
import { FullTranscript } from "@/components/report/FullTranscript";
import { MiaSuggestion } from "@/components/report/MiaSuggestion";
import { RubricScore } from "@/components/RubricScore";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { usePolling } from "@/hooks/usePolling";
import { useSessionView } from "@/hooks/useSessionView";
import { ApiError, apiRequest } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { formatDateLong, formatMinutes, formatScore } from "@/lib/format";
import { countQuestions, questionNumbers } from "@/lib/interview";
import { interviewName } from "@/lib/labels";
import { durationMinutes, previousAttempt } from "@/lib/report";
import { routeForStatus } from "@/lib/routes";
import type { ReportView, Session, SessionView } from "@/lib/types";

const LOAD_ERROR = "Não foi possível carregar o feedback.";

/** Design section 6.6: overall score → competencies → what to improve → the rest. */
export function ReportPage() {
  useDocumentTitle("Relatório");
  const { id = "" } = useParams();
  const { view, setView, reload } = useSessionView(id, ["scoring", "completed"]);

  if (view.state === "not_found") return <SessionNotFound />;
  return (
    <>
      <AppHeader role="candidate" />
      <main className="mx-auto flex max-w-[760px] flex-col gap-12 px-4 py-12 md:px-6">
        {view.state === "loading" && <ReportSkeleton />}
        {view.state === "error" && <LoadError onRetry={reload} />}
        {view.state === "ready" && view.view.session.status === "scoring" && (
          <Scoring id={id} onCompleted={(data) => setView({ state: "ready", view: data })} />
        )}
        {view.state === "ready" && view.view.session.status === "completed" && (
          <ReportLoader id={id} session={view.view.session} onInvalidState={reload} />
        )}
      </main>
    </>
  );
}

function LoadError({ onRetry, text = LOAD_ERROR }: { onRetry: () => void; text?: string }) {
  return (
    <InlineNotice variant="danger" action={{ label: "Tentar de novo", onClick: onRetry }}>
      {text}
    </InlineNotice>
  );
}

function ReportSkeleton() {
  return (
    <div data-testid="report-skeleton" className="flex flex-col gap-4" aria-hidden="true">
      <Skeleton className="h-3 w-32 rounded-md" />
      <Skeleton className="h-10 w-2/3 rounded-md" />
      <Skeleton className="h-3 w-1/2 rounded-md" />
      <Skeleton className="mt-8 h-14 w-48 rounded-md" />
      {[0, 1, 2].map((i) => (
        <Skeleton key={i} className="mt-4 h-3 w-full rounded-md" />
      ))}
    </div>
  );
}

function Scoring({ id, onCompleted }: { id: string; onCompleted: (view: SessionView) => void }) {
  const [failed, setFailed] = useState(false);
  const { offline } = usePolling(
    async () => {
      try {
        return await apiRequest<SessionView>("GET", `/sessions/${id}`);
      } catch (err) {
        if (!(err instanceof ApiError && err.code === "network")) setFailed(true);
        throw err;
      }
    },
    {
      enabled: !failed,
      onData: (data) => {
        if (data.session.status === "completed") onCompleted(data);
      },
    },
  );
  return (
    <div className="flex flex-col items-center gap-4 py-12 text-center">
      <MiaMark size={48} state="thinking" />
      <p className="text-body text-foreground-soft">
        A MIA está avaliando suas respostas. Isso costuma levar menos de um minuto.
      </p>
      {(failed || offline) && <LoadError onRetry={() => setFailed(false)} />}
    </div>
  );
}

type Loaded = { state: "loading" } | { state: "error"; text?: string } | { state: "ready"; data: ReportView; sessions: Session[] };

type ReportLoaderProps = { id: string; session: Session; onInvalidState: () => Promise<void> };

function ReportLoader({ id, session, onInvalidState }: ReportLoaderProps) {
  const [load, setLoad] = useState<Loaded>({ state: "loading" });

  const fetchAll = useCallback(async () => {
    setLoad({ state: "loading" });
    try {
      const [data, sessions] = await Promise.all([
        apiRequest<ReportView>("GET", `/sessions/${id}/report`),
        apiRequest<Session[]>("GET", "/sessions").catch(() => [] as Session[]),
      ]);
      setLoad({ state: "ready", data, sessions });
    } catch (err) {
      const error = err instanceof ApiError ? err : new ApiError("internal", true, null);
      if (error.code === "invalid_state") {
        // Design 10.1: toast, then get_session + routeForStatus (done by the session view).
        toast(errorMessage(error, "session_screen").text);
        void onInvalidState();
        return;
      }
      // Design 10.1: llm_invalid_output has its own text; the rest keeps the 6.6 load error.
      const text = error.code === "llm_invalid_output" ? errorMessage(error, "session_screen").text : undefined;
      setLoad({ state: "error", text });
    }
  }, [id, onInvalidState]);

  useEffect(() => {
    void fetchAll();
  }, [fetchAll]);

  if (load.state === "loading") return <ReportSkeleton />;
  if (load.state === "error") return <LoadError onRetry={fetchAll} text={load.text} />;
  return <ReportBody session={session} data={load.data} previous={previousAttempt(load.sessions, session)} />;
}

type ReportBodyProps = { session: Session; data: ReportView; previous: Session | null };

function ReportBody({ session, data, previous }: ReportBodyProps) {
  const { report, turns } = data;
  const minutes = durationMinutes(session.started_at, session.ended_at);
  const questions = countQuestions(turns);
  const meta = [
    interviewName(session.persona),
    formatDateLong(session.ended_at ?? session.created_at),
    minutes === null ? null : formatMinutes(minutes),
    `${questions} ${questions === 1 ? "pergunta" : "perguntas"}`,
  ].filter(Boolean);
  const numbers = questionNumbers(turns);

  return (
    <>
      <section className="flex flex-col gap-3">
        <p className="label text-mia">Feedback da MIA</p>
        <h1 className="text-h1">{session.job_title ?? "Vaga sem título"}</h1>
        <p className="text-small text-muted-foreground">{meta.join(" · ")}</p>
      </section>

      <section className="flex flex-col gap-4">
        <div data-testid="overall-score" className="flex flex-col gap-2">
          <h2 className="label font-mono text-muted-foreground">Nota geral</h2>
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
            <p className="flex items-baseline gap-2">
              <span className="font-serif text-display tabular-nums max-md:text-[2.5rem]">
                {formatScore(report.overall_score)}
              </span>
              <span className="text-h2 text-muted-foreground">de 5</span>
            </p>
            <RubricScore score={report.overall_score} size="md" showLabel showNumber={false} />
          </div>
          {previous?.overall_score != null && (
            <p className="text-small text-muted-foreground">
              {`Tentativa anterior neste caso: ${formatScore(previous.overall_score)}`}
            </p>
          )}
        </div>
        {data.is_above_case_avg === true && <AboveAverageNote sessionId={session.session_id} />}
        {data.examples_seen && (
          <p className="text-small text-muted-foreground">Sugestões de resposta vistas nesta simulação.</p>
        )}
      </section>

      <section className="flex flex-col gap-6">
        <h2 className="text-h2">Por competência</h2>
        <div className="flex flex-col gap-6">
          {report.competencies.map((c) => (
            <CompetencyRow key={c.competency} item={c} before={previous?.competency_scores?.[c.competency]} />
          ))}
        </div>
      </section>

      <section className="flex flex-col gap-4">
        <h2 className="text-h2">O que funcionou</h2>
        <ul className="flex flex-col gap-2">
          {report.strengths.map((s) => (
            <li key={s} className="flex items-start gap-2 text-body">
              <Check className="mt-1 size-4 shrink-0 text-mia" aria-hidden="true" />
              {s}
            </li>
          ))}
        </ul>
      </section>

      <section className="flex flex-col gap-4">
        <h2 className="text-h2">O que melhorar</h2>
        {report.improvements.length === 0 ? (
          <p className="text-body text-muted-foreground">Nenhum ponto crítico nesta entrevista.</p>
        ) : (
          report.improvements.map((item) => (
            <article
              key={item.question_id}
              data-testid={`improvement-${item.question_id}`}
              className="flex flex-col gap-3 rounded-lg border border-border bg-card p-6"
            >
              <p className="label text-muted-foreground">{`Pergunta ${numbers.get(item.question_id) ?? "?"}`}</p>
              <p className="font-serif text-[1.125rem] leading-7">
                {turns.find((t) => t.question_id === item.question_id)?.interviewer_text}
              </p>
              <p className="text-body text-foreground-soft">{`O que faltou: ${item.issue}`}</p>
              <MiaSuggestion text={item.stronger_answer} />
            </article>
          ))
        )}
      </section>

      <section className="flex flex-col gap-4">
        <h2 className="text-h2">Resposta por resposta</h2>
        <AnswerByAnswer turns={turns} persona={session.persona} />
      </section>

      <FullTranscript turns={turns} persona={session.persona} />

      <Actions session={session} />
    </>
  );
}

const BLOCKING = new Set(["quota_exceeded", "demo_paused"]);

/** "Treinar este caso de novo" respects the quotas, like the CaseDialog (10.1). */
function Actions({ session }: { session: Session }) {
  const navigate = useNavigate();
  const [creating, setCreating] = useState(false);
  const [blocked, setBlocked] = useState<ApiError | null>(null);
  const caseId = session.case_id;

  async function trainAgain() {
    if (!caseId || creating || blocked) return;
    setCreating(true);
    try {
      const created = await apiRequest<Session>("POST", "/sessions", { case_id: caseId, mode: session.mode });
      navigate(routeForStatus(created.status, created.session_id).path);
    } catch (err) {
      setCreating(false);
      if (!(err instanceof ApiError)) return;
      if (BLOCKING.has(err.code)) setBlocked(err);
      else toast(errorMessage(err, "case_dialog").text);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {blocked && <InlineNotice variant="warning">{errorMessage(blocked, "case_dialog").text}</InlineNotice>}
      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-between">
        <Button variant="outline" className="w-full sm:w-auto" onClick={() => navigate("/")}>
          Voltar ao início
        </Button>
        {caseId && (
          <Button
            className="w-full sm:w-auto"
            aria-disabled={creating || blocked !== null}
            aria-busy={creating}
            onClick={() => void trainAgain()}
          >
            {creating && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
            {creating ? "Criando…" : "Treinar este caso de novo"}
          </Button>
        )}
      </div>
    </div>
  );
}
