import type { Case, CaseSummary, Screening, Session, SessionView } from "@/lib/types";

export function makeFullCase(overrides: Partial<Case> = {}): Case {
  return {
    case_id: "prompt-engineer-jr",
    title: "Engenheiro(a) de Prompt Jr",
    company: "Nexa Consultoria",
    level: "junior",
    persona: "technical",
    language: "pt-BR",
    blurb: "Vaga para construir prompts e avaliações.",
    candidate_blurb: "Você é Ana, recém-formada em Sistemas de Informação.",
    estimated_minutes: 20,
    version: 1,
    ...overrides,
  };
}

export function makeScreening(overrides: Partial<Screening> = {}): Screening {
  return {
    job_title: "Engenheiro(a) de Prompt Jr",
    fit_score: 72,
    strengths: [{ point: "Já fez RAG", cv_quote: "chatbot com RAG sobre 3 fontes" }],
    concerns: [{ point: "Pouca avaliação", cv_quote: "testes manuais" }],
    missing_keywords: ["LangGraph", "Bedrock"],
    competencies: ["Engenharia de prompts", "Avaliação de modelos", "Comunicação técnica"],
    ...overrides,
  };
}

export function makeView(overrides: Partial<SessionView> = {}, session: Partial<Session> = {}): SessionView {
  return {
    session: makeSession(session),
    case: makeFullCase(),
    screening: makeScreening(),
    turns: null,
    ...overrides,
  };
}

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
