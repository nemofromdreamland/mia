// Test helpers for the report screen.
import { render } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { Toaster } from "@/components/ui/sonner";
import type { ReportView, Session, Turn } from "@/lib/types";
import { routes } from "@/router";
import { makeSession, makeView } from "@/test/data";

export function fullTurn(n: number, qid: string, overrides: Partial<Turn> = {}): Turn {
  return {
    session_id: "s1",
    turn_no: n,
    question_id: qid,
    interviewer_text: `Pergunta do turno ${n}?`,
    answer_text: `Resposta ${n} com medi recall antes e depois.`,
    is_follow_up: false,
    score: {
      score: 4,
      criteria_met: ["métrica definida"],
      evidence_quotes: ["medi recall antes e depois"],
      justification: `Justificativa ${n}.`,
      quotes_verified: true,
    },
    created_at: "2026-11-15T10:00:00Z",
    ...overrides,
  };
}

export function makeReportView(overrides: Partial<ReportView> = {}): ReportView {
  return {
    report: {
      overall_score: 3.8,
      competencies: [
        { competency: "Engenharia de prompts", score: 4, summary: "Estrutura bem os prompts." },
        { competency: "Avaliação de modelos", score: 3, summary: "Mede, mas sem limitações." },
      ],
      strengths: ["Respostas com números concretos"],
      improvements: [{ question_id: "q2", issue: "não citou limitações da métrica.", stronger_answer: "Medi recall@5…" }],
    },
    turns: [
      fullTurn(1, "q1"),
      fullTurn(2, "q1", { is_follow_up: true, interviewer_text: "E o baseline?" }),
      fullTurn(3, "q2", { interviewer_text: "Como você mediu se a recuperação estava boa?" }),
    ],
    is_above_case_avg: null,
    ...overrides,
  };
}

export const COMPLETED: Partial<Session> = {
  status: "completed",
  overall_score: 3.8,
  created_at: "2026-11-15T10:00:00Z",
  started_at: "2026-11-15T10:00:00Z",
  ended_at: "2026-11-15T10:18:20Z",
};

export function completedView() {
  return makeView({ screening: null }, COMPLETED);
}

export const PREVIOUS = makeSession({
  session_id: "old",
  status: "completed",
  overall_score: 3.2,
  competency_scores: { "Engenharia de prompts": 3.5 },
  created_at: "2026-11-10T10:00:00Z",
});

export function renderReport() {
  const router = createMemoryRouter(routes, { initialEntries: ["/sessao/s1/relatorio"] });
  render(
    <>
      <RouterProvider router={router} />
      <Toaster />
    </>,
  );
  return router;
}
