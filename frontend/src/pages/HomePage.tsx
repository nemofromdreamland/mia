import { useCallback, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { AppHeader } from "@/components/AppHeader";
import { CaseCard } from "@/components/CaseCard";
import { CaseDialog } from "@/components/CaseDialog";
import { InlineNotice } from "@/components/InlineNotice";
import { Skeleton } from "@/components/ui/skeleton";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { ApiError, apiRequest } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { routeForStatus } from "@/lib/routes";
import type { CaseSummary, Session } from "@/lib/types";
import { isStorageAvailable } from "@/lib/visitor";

type Load<T> = { state: "loading" } | { state: "error" } | { state: "ready"; data: T };

/** Design section 6.1: cases + history of this browser. */
export function HomePage() {
  useDocumentTitle("Suas simulações");
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [cases, setCases] = useState<Load<CaseSummary[]>>({ state: "loading" });
  const [blocked, setBlocked] = useState<ApiError | null>(null);
  const [storageOk] = useState(isStorageAvailable);

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
      </main>
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
