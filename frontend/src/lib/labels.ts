// pt-BR labels from Design sections 5.6, 5.8, 5.14 and 5.30.
import type { Level, Persona, SessionStatus } from "./types";

const PERSONA_SHORT: Record<Persona, string> = { hr: "RH", technical: "TÉCNICA", manager: "GESTÃO" };
const PERSONA_COLUMN: Record<Persona, string> = { hr: "RH", technical: "Técnica", manager: "Gestão" };
const INTERVIEW_NAME: Record<Persona, string> = {
  hr: "Triagem de RH",
  technical: "Entrevista técnica",
  manager: "Conversa com gestão",
};
const LEVEL: Record<Level, string> = { internship: "ESTÁGIO", junior: "JÚNIOR", mid: "PLENO" };
const STATUS: Record<SessionStatus, string> = {
  preparing: "PREPARANDO",
  ready: "PRONTA",
  in_progress: "EM ANDAMENTO",
  scoring: "EM AVALIAÇÃO",
  completed: "CONCLUÍDA",
  failed: "FALHOU",
  abandoned: "ABANDONADA",
};
const RUBRIC = ["Não atende", "Atende pouco", "Atende em parte", "Atende bem", "Atende plenamente"];

export function personaLabel(p: Persona): string {
  return PERSONA_SHORT[p];
}

/** Persona name for table columns ("Técnica"). */
export function personaColumn(p: Persona): string {
  return PERSONA_COLUMN[p];
}

export function interviewName(p: Persona): string {
  return INTERVIEW_NAME[p];
}

export function levelLabel(l: Level): string {
  return LEVEL[l];
}

/** Level in sentence case for running text ("Júnior"). */
export function levelText(l: Level): string {
  const upper = LEVEL[l];
  return upper.charAt(0) + upper.slice(1).toLowerCase();
}

export function statusLabel(s: SessionStatus): string {
  return STATUS[s];
}

export function rubricLabel(score: number): string {
  const rounded = Math.min(5, Math.max(1, Math.round(score)));
  return RUBRIC[rounded - 1];
}
