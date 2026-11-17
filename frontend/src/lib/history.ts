// Pure helpers for the home history (Design 5.7 and 9.2).
import { formatDateShort, formatScore } from "./format";
import type { CaseSummary, Persona, Session } from "./types";

const MAX_POINTS = 20;

export type Point = {
  label: string;
  score: number;
  persona: Persona;
  title: string;
  date: string;
};

export function chartPoints(sessions: Session[]): Point[] {
  const done = sessions
    .filter((s) => s.status === "completed" && s.overall_score !== null)
    .sort((a, b) => (a.ended_at ?? a.created_at).localeCompare(b.ended_at ?? b.created_at))
    .slice(-MAX_POINTS);
  const perDay = new Map<string, number>();
  return done.map((s) => {
    const iso = s.ended_at ?? s.created_at;
    const day = formatDateShort(iso).slice(0, 5);
    const n = (perDay.get(day) ?? 0) + 1;
    perDay.set(day, n);
    return {
      label: n > 1 ? `${day} (${n})` : day,
      score: s.overall_score as number,
      persona: s.persona,
      title: s.job_title ?? "Vaga sem título",
      date: formatDateShort(iso),
    };
  });
}

export function chartSummary(points: Point[]): string {
  const scores = points.map((p) => p.score);
  const min = formatScore(Math.min(...scores));
  const max = formatScore(Math.max(...scores));
  const last = formatScore(scores[scores.length - 1]);
  return `Nota geral de ${points.length} simulações concluídas, de ${min} a ${max}. Última: ${last}.`;
}

export function sessionTitle(s: Session, cases: CaseSummary[]): string {
  return cases.find((c) => c.case_id === s.case_id)?.title ?? s.job_title ?? "Vaga sem título";
}

