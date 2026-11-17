import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { ArrowLeft } from "lucide-react";
import { AppHeader } from "@/components/AppHeader";
import { EvidenceQuote } from "@/components/EvidenceQuote";
import { FullPageState } from "@/components/FullPageState";
import { InlineNotice } from "@/components/InlineNotice";
import { NextStepTag } from "@/components/recruiter/NextStepTag";
import { CompetencyRow } from "@/components/report/CompetencyRow";
import { FullTranscript } from "@/components/report/FullTranscript";
import { RubricScore } from "@/components/RubricScore";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { ApiError, apiRequest } from "@/lib/api";
import { formatDateLong, formatMinutes, formatScore } from "@/lib/format";
import { formatDelta, interviewName } from "@/lib/labels";
import { durationMinutes } from "@/lib/report";
import type { CaseSummary, RecruiterCandidate, SummaryPoint } from "@/lib/types";

type Load =
  | { state: "loading" }
  | { state: "not_found" }
  | { state: "error" }
  | { state: "ready"; data: RecruiterCandidate; caseInfo: CaseSummary | null };

/** Design section 6.8: one anonymous candidate and the suggested next step (support, not decision). */
export function CandidatePage() {
  const { id = "" } = useParams();
  const [load, setLoad] = useState<Load>({ state: "loading" });
  useDocumentTitle(load.state === "ready" ? `Candidato ${load.data.row.candidate_no}` : "Candidato");

  const fetchAll = useCallback(async () => {
    setLoad({ state: "loading" });
    try {
      const [data, cases] = await Promise.all([
        apiRequest<RecruiterCandidate>("GET", `/recruiter/candidates/${id}`),
        apiRequest<CaseSummary[]>("GET", "/cases").catch(() => [] as CaseSummary[]),
      ]);
      setLoad({ state: "ready", data, caseInfo: cases.find((c) => c.case_id === data.row.case_id) ?? null });
    } catch (err) {
      setLoad(err instanceof ApiError && err.code === "not_found" ? { state: "not_found" } : { state: "error" });
    }
  }, [id]);

  useEffect(() => {
    void fetchAll();
  }, [fetchAll]);

  if (load.state === "not_found") {
    return (
      <FullPageState
        role="recruiter"
        title="Este candidato não está mais disponível."
        action={{ label: "Voltar aos candidatos", to: "/recrutador" }}
      />
    );
  }
  return (
    <>
      <AppHeader role="recruiter" />
      <main className="mx-auto flex max-w-[760px] flex-col gap-12 px-4 py-12 md:px-6">
        <Link to="/recrutador" className="inline-flex items-center gap-2 text-small text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-4" aria-hidden="true" />
          Candidatos
        </Link>
        {load.state === "loading" && <CandidateSkeleton />}
        {load.state === "error" && (
          <InlineNotice variant="danger" action={{ label: "Tentar de novo", onClick: fetchAll }}>
            Não foi possível carregar o candidato.
          </InlineNotice>
        )}
        {load.state === "ready" && <CandidateBody data={load.data} caseInfo={load.caseInfo} />}
      </main>
    </>
  );
}

function CandidateSkeleton() {
  return (
    <div data-testid="candidate-skeleton" className="flex flex-col gap-4" aria-hidden="true">
      <Skeleton className="h-3 w-48 rounded-md" />
      <Skeleton className="h-10 w-3/4 rounded-md" />
      <Skeleton className="h-3 w-1/2 rounded-md" />
      <Skeleton className="mt-8 h-14 w-48 rounded-md" />
      {[0, 1, 2].map((i) => (
        <Skeleton key={i} className="mt-4 h-12 w-full rounded-md" />
      ))}
    </div>
  );
}

type BodyProps = { data: RecruiterCandidate; caseInfo: CaseSummary | null };

function CandidateBody({ data, caseInfo }: BodyProps) {
  const navigate = useNavigate();
  const { row, summary, report, turns } = data;
  const minutes = durationMinutes(turns[0]?.created_at, row.ended_at);
  const meta = [
    caseInfo ? interviewName(caseInfo.persona) : null,
    formatDateLong(row.ended_at),
    minutes === null ? null : formatMinutes(minutes),
  ].filter(Boolean);
  const delta = row.delta_vs_case_avg;
  const answers = turns.map((t) => t.answer_text ?? "");

  return (
    <>
      <section className="flex flex-col gap-3">
        <p className="label text-muted-foreground">
          {caseInfo ? `Candidato ${row.candidate_no} · ${caseInfo.title}` : `Candidato ${row.candidate_no}`}
        </p>
        <h1 className="text-h1">{summary.headline}</h1>
        <p className="text-small text-muted-foreground">{meta.join(" · ")}</p>
        {data.examples_seen && (
          <p className="text-small text-muted-foreground">Exemplos vistos nesta simulação.</p>
        )}
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="label font-mono text-muted-foreground">Nota geral</h2>
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
          <p className="flex items-baseline gap-2">
            <span className="font-serif text-display tabular-nums max-md:text-[2.5rem]">
              {formatScore(row.overall_score)}
            </span>
            <span className="text-h2 text-muted-foreground">de 5</span>
          </p>
          <RubricScore score={row.overall_score} size="md" showLabel showNumber={false} />
        </div>
        <p className="font-mono text-small text-muted-foreground">
          {delta === null
            ? "Média ainda não calculada"
            : `${formatDelta(delta)} acima da média do caso (${formatScore(row.overall_score - delta)})`}
        </p>
      </section>

      <section data-testid="candidate-summary" className="flex flex-col gap-3">
        <h2 className="text-h2">Resumo</h2>
        <p className="text-answer text-foreground-soft">{summary.summary}</p>
      </section>

      <div className="grid grid-cols-1 gap-12 md:grid-cols-2 md:gap-6">
        <PointList title="Pontos fortes" items={summary.strengths} answers={answers} />
        <PointList title="Pontos de atenção" items={summary.concerns} answers={answers} />
      </div>

      <section className="flex flex-col gap-6">
        <h2 className="text-h2">Por competência</h2>
        <div className="flex flex-col gap-6">
          {report.competencies.map((c) => (
            <CompetencyRow key={c.competency} item={c} />
          ))}
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-h2">Próximo passo sugerido</h2>
        <div>
          <NextStepTag step={summary.suggested_next_step} />
        </div>
        <p className="text-body text-foreground-soft">{summary.next_step_reason}</p>
        <p className="text-small text-muted-foreground">Apoio à decisão. Quem decide é você.</p>
      </section>

      <FullTranscript turns={turns} persona={caseInfo?.persona ?? "technical"} />

      <div>
        <Button variant="outline" className="w-full sm:w-auto" onClick={() => navigate("/recrutador")}>
          Voltar aos candidatos
        </Button>
      </div>
    </>
  );
}

type PointListProps = { title: string; items: SummaryPoint[]; answers: string[] };

/** Points with their quote; a quote that is not literally in an answer is dropped (6.8). */
function PointList({ title, items, answers }: PointListProps) {
  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-h2">{title}</h2>
      {items.map((item) => (
        <div key={item.point} className="flex flex-col gap-2">
          <h3 className="text-h3">{item.point}</h3>
          <EvidenceQuote
            label="DA RESPOSTA"
            quote={item.answer_quote}
            verified={answers.some((a) => a.includes(item.answer_quote))}
          />
        </div>
      ))}
    </section>
  );
}
