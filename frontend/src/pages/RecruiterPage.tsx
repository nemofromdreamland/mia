import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { AppHeader } from "@/components/AppHeader";
import { InlineNotice } from "@/components/InlineNotice";
import { CaseFilter } from "@/components/recruiter/CaseFilter";
import { RecruiterRow } from "@/components/recruiter/RecruiterRow";
import { Skeleton } from "@/components/ui/skeleton";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { apiRequest } from "@/lib/api";
import { formatScore } from "@/lib/format";
import type { CaseStats, CaseSummary, RecruiterCandidateRow, RecruiterList } from "@/lib/types";

type Load = { state: "loading" } | { state: "error" } | { state: "ready"; list: RecruiterList; cases: CaseSummary[] };

/** Design section 6.7: per case, who scored above that case's average (anonymous). */
export function RecruiterPage() {
  useDocumentTitle("Candidatos");
  const [params, setParams] = useSearchParams();
  const caseId = params.get("caso");
  const [load, setLoad] = useState<Load>({ state: "loading" });
  const [cases, setCases] = useState<CaseSummary[]>([]);

  const fetchAll = useCallback(async () => {
    setLoad({ state: "loading" });
    const query = caseId ? `?case_id=${encodeURIComponent(caseId)}` : "";
    try {
      const [list, caseList] = await Promise.all([
        apiRequest<RecruiterList>("GET", `/recruiter/candidates${query}`),
        apiRequest<CaseSummary[]>("GET", "/cases"),
      ]);
      setCases(caseList);
      setLoad({ state: "ready", list, cases: caseList });
    } catch {
      setLoad({ state: "error" });
    }
  }, [caseId]);

  useEffect(() => {
    void fetchAll();
  }, [fetchAll]);

  return (
    <>
      <AppHeader role="recruiter" />
      <main className="mx-auto flex max-w-[1040px] flex-col gap-12 px-4 py-12 md:px-6">
        <section className="flex flex-col gap-3">
          <p className="label text-muted-foreground">Tela do recrutador</p>
          <h1 className="text-h1">Candidatos acima da média</h1>
          <p className="text-body text-muted-foreground">
            Entrevistas feitas nesta demo, anônimas. Cada caso tem a sua média.
          </p>
          <CaseFilter
            cases={cases}
            value={caseId}
            onChange={(id) => setParams(id ? { caso: id } : {})}
          />
        </section>

        {load.state === "loading" &&
          Array.from({ length: caseId ? 1 : 5 }, (_, i) => <GroupSkeleton key={i} />)}
        {load.state === "error" && (
          <InlineNotice variant="danger" action={{ label: "Tentar de novo", onClick: fetchAll }}>
            Não foi possível carregar os candidatos.
          </InlineNotice>
        )}
        {load.state === "ready" &&
          load.cases
            .map((c) => ({ item: c, stats: load.list.stats.find((s) => s.case_id === c.case_id) }))
            .filter((g): g is { item: CaseSummary; stats: CaseStats } => g.stats !== undefined)
            .map(({ item, stats }) => (
              <CaseGroup
                key={item.case_id}
                item={item}
                stats={stats}
                rows={load.list.candidates.filter((r) => r.case_id === item.case_id)}
              />
            ))}

        <p className="text-small text-muted-foreground">
          Os resumos são gerados pela MIA a partir das respostas da entrevista. São apoio à decisão: quem decide é
          você.
        </p>
      </main>
    </>
  );
}

function GroupSkeleton() {
  return (
    <div data-testid="recruiter-skeleton" className="flex flex-col gap-3" aria-hidden="true">
      <Skeleton className="h-6 w-1/2 rounded-md" />
      {[0, 1, 2].map((i) => (
        <Skeleton key={i} className="h-3 w-full rounded-md" />
      ))}
    </div>
  );
}

function countText(n: number): string {
  return n === 1 ? "1 entrevista concluída" : `${n} entrevistas concluídas`;
}

type CaseGroupProps = { item: CaseSummary; stats: CaseStats; rows: RecruiterCandidateRow[] };

function CaseGroup({ item, stats, rows }: CaseGroupProps) {
  const titleId = `case-${item.case_id}`;
  const average = stats.average_score;
  const subtitle =
    average === null
      ? `Média ainda não calculada · ${countText(stats.completed_sessions)}`
      : `Média do caso ${formatScore(average)} · ${countText(stats.completed_sessions)}`;
  return (
    <section aria-labelledby={titleId} className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <h2 id={titleId} className="text-h2">{`${item.title} · ${item.company}`}</h2>
        <p className="font-mono text-small text-muted-foreground">{subtitle}</p>
      </div>
      {stats.completed_sessions === 0 ? (
        <p className="text-body text-muted-foreground">
          Ninguém concluiu este caso ainda.{" "}
          <Link to={`/?caso=${item.case_id}`} className="text-mia underline-offset-4 hover:underline">
            Fazer este caso
          </Link>
        </p>
      ) : (
        <>
          {average === null && (
            <InlineNotice variant="neutral">Mostrando todos os concluídos até haver 3 entrevistas.</InlineNotice>
          )}
          {rows.length === 0 ? (
            <p className="text-body text-muted-foreground">Nenhum candidato acima da média neste caso por enquanto.</p>
          ) : (
            <table className="w-full text-body md:table-fixed">
              <thead className="hidden md:table-header-group">
                <tr className="label text-left text-muted-foreground">
                  <th className="w-[140px] py-2 font-medium">Candidato</th>
                  <th className="w-[120px] py-2 font-medium">Data</th>
                  <th className="w-[140px] py-2 font-medium">Nota</th>
                  <th className="w-[130px] py-2 font-medium">Acima da média</th>
                  <th className="py-2 font-medium">Resumo</th>
                  <th className="w-[150px] py-2 font-medium">
                    <span className="sr-only">Ações</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <RecruiterRow key={row.session_id} row={row} />
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </section>
  );
}
