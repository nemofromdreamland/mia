import { Fragment, useEffect, useRef, useState, type ReactNode } from "react";
import { useNavigate, useParams } from "react-router";
import { toast } from "sonner";
import { SessionNotFound } from "@/components/FullPageState";
import { InlineNotice } from "@/components/InlineNotice";
import { AnswerComposer } from "@/components/interview/AnswerComposer";
import { InterviewHeader } from "@/components/interview/InterviewHeader";
import { QuestionDivider } from "@/components/interview/QuestionDivider";
import { TranscriptTurn } from "@/components/interview/TranscriptTurn";
import { TypingIndicator } from "@/components/interview/TypingIndicator";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useSessionView } from "@/hooks/useSessionView";
import { ApiError, apiRequest } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { countQuestions, questionNumbers } from "@/lib/interview";
import type { AnswerResult, PublicTurn, SessionView } from "@/lib/types";

const SLOW_AFTER_MS = 15_000;
const DRAFT_DELAY_MS = 500;

/** Design section 6.5: one question at a time, nothing that grades the visitor. */
export function InterviewPage() {
  useDocumentTitle("Entrevista");
  const { id = "" } = useParams();
  const { view, reload } = useSessionView(id, ["in_progress"]);

  if (view.state === "not_found") return <SessionNotFound />;
  if (view.state === "ready") return <Interview id={id} view={view.view} reload={reload} />;
  return (
    <Layout header={<div className="h-14 shrink-0 border-b border-border" />}>
      {view.state === "loading" ? (
        <div data-testid="interview-skeleton" className="flex flex-col gap-8" aria-hidden="true">
          {[0, 1].map((i) => (
            <div key={i} className="flex flex-col gap-3">
              <Skeleton className="h-3 w-40 rounded-md" />
              <Skeleton className="h-3 w-full rounded-md" />
              <Skeleton className="h-3 w-4/5 rounded-md" />
            </div>
          ))}
        </div>
      ) : (
        <InlineNotice variant="danger" action={{ label: "Tentar de novo", onClick: reload }}>
          {errorMessage(view.error, "session_screen").text}
        </InlineNotice>
      )}
      <Footer>
        <AnswerComposer value="" onChange={() => {}} onSend={() => {}} sending={false} disabled />
      </Footer>
    </Layout>
  );
}

function Layout({ header, children }: { header: ReactNode; children: ReactNode }) {
  const items = Array.isArray(children) ? children : [children];
  return (
    <div className="flex h-[100dvh] flex-col">
      {header}
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto flex max-w-[680px] flex-col gap-8 px-4 py-8 md:px-6">{items[0]}</div>
      </main>
      {items.slice(1)}
    </div>
  );
}

function Footer({ children }: { children: ReactNode }) {
  return (
    <div className="shrink-0 border-t border-border bg-background p-4">
      <div className="mx-auto flex max-w-[680px] flex-col gap-3">{children}</div>
    </div>
  );
}

type Pending = { text: string; state: "sending" | "failed" };

function draftKey(id: string): string {
  return `mia:draft:${id}`;
}

function readDraft(id: string): string {
  try {
    return localStorage.getItem(draftKey(id)) ?? "";
  } catch {
    return "";
  }
}

function writeDraft(id: string, text: string): void {
  try {
    if (text) localStorage.setItem(draftKey(id), text);
    else localStorage.removeItem(draftKey(id));
  } catch {
    // Without storage the draft lives only in memory.
  }
}

type InterviewProps = { id: string; view: SessionView; reload: () => Promise<void> };

function Interview({ id, view, reload }: InterviewProps) {
  const navigate = useNavigate();
  const { session } = view;
  const [turns, setTurns] = useState<PublicTurn[]>(view.turns ?? []);
  const [pending, setPending] = useState<Pending | null>(null);
  const [draft, setDraft] = useState(() => readDraft(id));
  const [slow, setSlow] = useState(false);
  const [composerError, setComposerError] = useState<string | null>(null);
  const [providerDown, setProviderDown] = useState(false);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const lastMiaRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const slowTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => composerRef.current?.focus(), []);

  useEffect(() => {
    const timer = setTimeout(() => writeDraft(id, draft), DRAFT_DELAY_MS);
    return () => clearTimeout(timer);
  }, [id, draft]);

  useEffect(() => {
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, []);

  useEffect(() => {
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    lastMiaRef.current?.scrollIntoView?.({ block: "start", behavior: reduce ? "auto" : "smooth" });
  }, [turns.length]);

  useEffect(() => () => abortRef.current?.abort(), []);

  async function send(text: string) {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    clearTimeout(slowTimer.current);
    slowTimer.current = setTimeout(() => setSlow(true), SLOW_AFTER_MS);
    setPending({ text, state: "sending" });
    setSlow(false);
    setComposerError(null);
    setProviderDown(false);
    setDraft("");
    writeDraft(id, "");
    try {
      const result = await apiRequest<AnswerResult>(
        "POST",
        `/sessions/${id}/turns`,
        { answer_text: text },
        { signal: controller.signal },
      );
      if (controller.signal.aborted) return;
      setTurns((list) => [
        ...list.slice(0, -1),
        ...list.slice(-1).map((t) => ({ ...t, answer_text: text })),
        ...(result.turn ? [result.turn] : []),
      ]);
      setPending(null);
    } catch (err) {
      if (controller.signal.aborted) return;
      fail(err instanceof ApiError ? err : new ApiError("internal", true, null), text);
    } finally {
      if (!controller.signal.aborted) {
        clearTimeout(slowTimer.current);
        setSlow(false);
      }
    }
  }

  function fail(error: ApiError, text: string) {
    setDraft(text);
    if (error.code === "invalid_input") {
      setPending(null);
      setComposerError(errorMessage(error, "interview_answer").text);
      return;
    }
    setPending({ text, state: "failed" });
    if (error.code === "provider_unavailable") {
      setProviderDown(true);
      return;
    }
    toast(errorMessage(error, "interview").text);
    if (error.code === "invalid_state") void reload();
  }

  const numbers = questionNumbers(turns);
  const last = turns.length - 1;
  const sending = pending?.state === "sending";

  return (
    <Layout
      header={
        <InterviewHeader
          persona={session.persona}
          jobTitle={session.job_title}
          questions={countQuestions(turns)}
          startedAt={session.started_at ?? null}
          onEnd={() => {}}
        />
      }
    >
      <div data-testid="transcript" className="flex flex-col gap-8">
        {turns.map((t, i) => (
          <Fragment key={t.turn_no}>
            {i > 0 && t.question_id !== turns[i - 1].question_id && (
              <QuestionDivider n={numbers.get(t.question_id) ?? i + 1} />
            )}
            <TranscriptTurn
              ref={i === last ? lastMiaRef : undefined}
              variant="mia"
              persona={session.persona}
              text={t.interviewer_text}
            />
            {t.answer_text && <TranscriptTurn variant="candidate" persona={session.persona} text={t.answer_text} />}
            {i === last && pending && (
              <TranscriptTurn
                variant={pending.state === "sending" ? "candidate-sending" : "candidate-failed"}
                persona={session.persona}
                text={pending.text}
                onRetry={() => void send(pending.text)}
              />
            )}
          </Fragment>
        ))}
        {sending && <TypingIndicator slow={slow} onResend={() => pending && void send(pending.text)} />}
      </div>
      <Footer>
        {providerDown && pending && (
          <InlineNotice variant="danger">
            <p>{errorMessage(new ApiError("provider_unavailable", true, null), "interview").text}</p>
            <div className="mt-2 flex gap-4">
              <Button variant="link" size="sm" className="h-auto p-0" onClick={() => void send(pending.text)}>
                Tentar de novo
              </Button>
              <Button variant="link" size="sm" className="h-auto p-0" onClick={() => navigate("/")}>
                Voltar ao início
              </Button>
            </div>
          </InlineNotice>
        )}
        <AnswerComposer
          ref={composerRef}
          value={draft}
          onChange={(value) => {
            setDraft(value);
            setComposerError(null);
          }}
          onSend={() => void send(draft)}
          sending={sending}
          error={composerError}
        />
      </Footer>
    </Layout>
  );
}
