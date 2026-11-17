// Test helpers for the recruiter screens.
import { render } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { Toaster } from "@/components/ui/sonner";
import type { RecruiterCandidate, RecruiterCandidateRow, RecruiterList } from "@/lib/types";
import { routes } from "@/router";
import { fullTurn, makeReportView } from "@/test/report";

export function makeRow(overrides: Partial<RecruiterCandidateRow> = {}): RecruiterCandidateRow {
  return {
    session_id: "s7",
    case_id: "prompt-engineer-jr",
    candidate_no: 7,
    ended_at: "2026-11-15T10:18:00Z",
    overall_score: 4.2,
    delta_vs_case_avg: 0.8,
    headline: "Explica decisões com números, mas não cita limitações.",
    ...overrides,
  };
}

export function makeList(overrides: Partial<RecruiterList> = {}): RecruiterList {
  return {
    stats: [
      { case_id: "prompt-engineer-jr", completed_sessions: 12, average_score: 3.4 },
      { case_id: "data-analyst-pleno", completed_sessions: 2, average_score: null },
      { case_id: "backend-python-jr", completed_sessions: 0, average_score: null },
      { case_id: "ai-product-manager", completed_sessions: 5, average_score: 4.5 },
      { case_id: "software-intern", completed_sessions: 0, average_score: null },
    ],
    candidates: [
      makeRow(),
      makeRow({ session_id: "s3", candidate_no: 3, overall_score: 3.9, delta_vs_case_avg: 0.5, headline: "Estrutura bem." }),
      makeRow({ session_id: "d1", case_id: "data-analyst-pleno", candidate_no: 1, delta_vs_case_avg: null, headline: "Analisa bem." }),
    ],
    ...overrides,
  };
}

export function makeCandidate(overrides: Partial<RecruiterCandidate> = {}): RecruiterCandidate {
  const { report } = makeReportView();
  return {
    row: makeRow(),
    summary: {
      headline: "Explica decisões com números, mas não cita limitações.",
      summary: "Respondeu com exemplos concretos e mediu resultados.",
      strengths: [{ point: "Mede antes de afirmar", answer_quote: "medi recall antes e depois" }],
      concerns: [{ point: "Não discute limitações", answer_quote: "trecho que não existe" }],
      suggested_next_step: "advance_with_caution",
      next_step_reason: "Domina o básico de avaliação.",
    },
    report,
    turns: [
      fullTurn(1, "q1", { session_id: "s7", created_at: "2026-11-15T10:00:00Z" }),
      fullTurn(2, "q2", { session_id: "s7", created_at: "2026-11-15T10:05:00Z" }),
    ],
    ...overrides,
  };
}

export function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(
    <>
      <RouterProvider router={router} />
      <Toaster />
    </>,
  );
  return router;
}
