import type { CaseSummary, Session } from "@/lib/types";

export function makeCase(overrides: Partial<CaseSummary> = {}): CaseSummary {
  return {
    case_id: "prompt-engineer-jr",
    title: "Engenheiro(a) de Prompt Jr",
    company: "Nexa Consultoria",
    level: "junior",
    persona: "technical",
    blurb: "Vaga para construir prompts e avaliações.",
    candidate_blurb: "Você é Ana, recém-formada em SI.",
    estimated_minutes: 20,
    completed_sessions: 12,
    ...overrides,
  };
}

export const CASES: CaseSummary[] = [
  makeCase(),
  makeCase({ case_id: "data-analyst-pleno", title: "Analista de Dados Pleno", level: "mid", completed_sessions: 0 }),
  makeCase({ case_id: "backend-python-jr", title: "Desenvolvedor(a) Backend Python Jr", persona: "hr" }),
  makeCase({ case_id: "ai-product-manager", title: "Gerente de Produto de IA", persona: "manager", level: "mid" }),
  makeCase({ case_id: "software-intern", title: "Estágio em Software", level: "internship", persona: "hr" }),
];

export function makeSession(overrides: Partial<Session> = {}): Session {
  return {
    session_id: "s1",
    case_id: "prompt-engineer-jr",
    status: "ready",
    persona: "technical",
    language: "pt-BR",
    mode: "text",
    job_title: "Prompt Engineer Jr",
    fit_score: 72,
    overall_score: null,
    created_at: "2026-11-15T10:00:00Z",
    updated_at: "2026-11-15T10:00:00Z",
    ...overrides,
  };
}
