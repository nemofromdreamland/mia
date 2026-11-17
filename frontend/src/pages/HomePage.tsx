import { useCallback, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { AppHeader } from "@/components/AppHeader";
import { CaseCard } from "@/components/CaseCard";
import { CaseDialog } from "@/components/CaseDialog";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EvolutionChart } from "@/components/EvolutionChart";
import { InlineNotice } from "@/components/InlineNotice";
import { SessionList } from "@/components/SessionList";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { ApiError, apiRequest } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { routeForStatus } from "@/lib/routes";
import type { CaseSummary, Session } from "@/lib/types";
import { clearMiaStorage, isStorageAvailable, resetVisitorId } from "@/lib/visitor";
import { toast } from "sonner";

type Load<T> = { state: "loading" } | { state: "error" } | { state: "ready"; data: T };

/** Design section 6.1: cases + history of this browser. */
export function HomePage() {
  useDocumentTitle("Suas simulações");
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [cases, setCases] = useState<Load<CaseSummary[]>>({ state: "loading" });
  const [blocked, setBlocked] = useState<ApiError | null>(null);
  const [storageOk] = useState(isStorageAvailable);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [confirmAll, setConfirmAll] = useState(false);

  const loadSessions = useCallback(async () => {
    try {
      const list = await apiRequest<Session[]>("GET", "/sessions");
      setSessions([...list].sort((a, b) => b.created_at.localeCompare(a.created_at)));
    } catch (err) {
      if (err instanceof ApiError) toast.error(errorMessage(err, "home").text);
    }
  }, []);

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  async function deleteOne(session: Session) {
    try {
      await apiRequest("DELETE", `/sessions/${session.session_id}`);
      setSessions((list) => list.filter((s) => s.session_id !== session.session_id));
      toast("Simulação apagada.");
    } catch (err) {
      if (err instanceof ApiError) toast.error(errorMessage(err, "home").text);
    }
  }

  async function deleteAll() {
    setConfirmAll(false);
    try {
      for (const s of sessions) await apiRequest("DELETE", `/sessions/${s.session_id}`);
    } catch (err) {
      if (err instanceof ApiError) toast.error(errorMessage(err, "home").text);
      return void loadSessions();
    }
    clearMiaStorage();
    resetVisitorId();
    setSessions([]);
  }

  const completed = sessions.filter((s) => s.status === "completed" && s.overall_score !== null);

  const loadCases = useCallback(async () => {
    setCases({ state: "loading" });
    try {
      setCases({ state: "ready", data: await apiRequest<CaseSummary[]>("GET", "/cases") });
    } catch {
      setCases({ state: "error" });
    }
  }, []);

  useEffect(() => {
    void loadCases();
  }, [loadCases]);

  const openId = params.get("caso");
  const openCase = cases.state === "ready" ? (cases.data.find((c) => c.case_id === openId) ?? null) : null;

  function openDialog(caseId: string) {
    setParams({ caso: caseId });
  }

  function closeDialog() {
    setParams({});
  }

  function onCreated(session: Session) {
    navigate(routeForStatus(session.status, session.session_id).path);
  }

  return (
    <>
      <AppHeader role="candidate" />
      <main className="mx-auto flex max-w-[1040px] flex-col gap-12 px-4 py-12 md:px-6">
        <section className="flex flex-col gap-3">
          <h1 className="text-h1">Treine uma entrevista de emprego com a MIA</h1>
          <p className="max-w-[640px] text-body text-muted-foreground">
            Escolha um caso, responda como o candidato e receba uma avaliação por competência com trechos da
            sua própria fala. Sem cadastro.
          </p>
        </section>

        <section className="flex flex-col gap-4" aria-labelledby="cases-title">
          {blocked?.code === "demo_paused" && (
            <InlineNotice variant="warning">{errorMessage(blocked, "home").text}</InlineNotice>
          )}
          {!storageOk && (
            <InlineNotice variant="neutral">Seu histórico não será guardado neste navegador.</InlineNotice>
          )}
          <h2 id="cases-title" className="label font-mono text-muted-foreground">
            Escolha um caso
          </h2>
          {cases.state === "error" ? (
            <InlineNotice variant="danger" action={{ label: "Tentar de novo", onClick: loadCases }}>
              Não foi possível carregar os casos.
            </InlineNotice>
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
              {cases.state === "loading"
                ? Array.from({ length: 5 }, (_, i) => (
                    <Skeleton key={i} data-testid="case-skeleton" className="h-[180px] rounded-lg" />
                  ))
                : cases.data.map((item) => (
                    <CaseCard key={item.case_id} item={item} onOpen={() => openDialog(item.case_id)} />
                  ))}
            </div>
          )}
        </section>

        {sessions.length > 0 && (
          <section className="flex flex-col gap-4" aria-labelledby="history-title">
            <h2 id="history-title" className="text-h2">
              Suas simulações neste navegador
            </h2>
            {completed.length === 1 && (
              <div className="rounded-lg border border-border bg-card p-4 text-body text-muted-foreground">
                A evolução aparece a partir da segunda simulação concluída.
              </div>
            )}
            {completed.length >= 2 && <EvolutionChart sessions={sessions} />}
            <SessionList sessions={sessions} cases={cases.state === "ready" ? cases.data : []} onDelete={deleteOne} />
            <p className="text-small text-muted-foreground">
              Suas simulações ficam anônimas e ligadas só a este navegador.
            </p>
            <div>
              <Button
                variant="link"
                className="h-auto p-0"
                data-testid="delete-history"
                onClick={() => setConfirmAll(true)}
              >
                Apagar meu histórico
              </Button>
            </div>
          </section>
        )}
      </main>
      <ConfirmDialog
        open={confirmAll}
        title="Apagar seu histórico?"
        body="As simulações feitas neste navegador e os feedbacks serão apagados, inclusive da tela do recrutador. Isso não pode ser desfeito."
        confirmLabel="Apagar"
        onConfirm={deleteAll}
        onOpenChange={setConfirmAll}
      />
      <CaseDialog
        item={openCase}
        blocked={blocked}
        onClose={closeDialog}
        onCreated={onCreated}
        onBlocked={setBlocked}
      />
    </>
  );
}
