// pt-BR labels from Design sections 5.6, 5.8, 5.14 and 5.30.
import { formatScore } from "./format";
import type { Level, NextStep, Persona, SessionStatus } from "./types";

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

/** Fit label from Design section 5.15 (0–39 / 40–69 / 70–100). */
export function fitLabel(score: number): string {
  if (score < 40) return "Aderência baixa";
  if (score < 70) return "Aderência média";
  return "Aderência alta";
}

const NEXT_STEP: Record<NextStep, string> = {
  advance: "AVANÇAR PARA A PRÓXIMA ETAPA",
  advance_with_caution: "AVANÇAR COM RESSALVAS",
  not_now: "NÃO AVANÇAR AGORA",
};

/** NextStepTag text (Design 6.8). */
export function nextStepLabel(step: NextStep): string {
  return NEXT_STEP[step];
}

/** Difference to the case average, with sign: 0.8 → "+0,8" (no color, no arrow). */
export function formatDelta(delta: number): string {
  return `${delta >= 0 ? "+" : "−"}${formatScore(Math.abs(delta))}`;
}
