// Pure helpers for the Report screen (Design 6.6, 5.16 and 13).
import type { AnswerScore, Session, Turn } from "@/lib/types";

/** Latest completed session of the same visitor and case, created before `current`. */
export function previousAttempt(sessions: Session[], current: Session): Session | null {
  if (!current.case_id) return null;
  const earlier = sessions.filter(
    (s) =>
      s.session_id !== current.session_id &&
      s.case_id === current.case_id &&
      s.status === "completed" &&
      s.created_at < current.created_at,
  );
  earlier.sort((a, b) => b.created_at.localeCompare(a.created_at));
  return earlier[0] ?? null;
}

export type QuestionGroup = { questionId: string; n: number; turns: Turn[] };

export function groupByQuestion(turns: Turn[]): QuestionGroup[] {
  const groups: QuestionGroup[] = [];
  for (const turn of turns) {
    let group = groups.find((g) => g.questionId === turn.question_id);
    if (!group) {
      group = { questionId: turn.question_id, n: groups.length + 1, turns: [] };
      groups.push(group);
    }
    group.turns.push(turn);
  }
  return groups;
}

/** Quotes that may be highlighted: verified and literally present in the answer. */
export function verifiedQuotes(answer: string, score: AnswerScore | null): string[] {
  if (!score || score.quotes_verified === false) return [];
  return score.evidence_quotes.filter((q) => q && answer.includes(q));
}

export type Segment = { text: string; mark: boolean };

/** Splits `answer` into plain and highlighted parts; overlapping quotes are skipped. */
export function highlight(answer: string, quotes: string[]): Segment[] {
  const ranges: [number, number][] = [];
  for (const quote of quotes) {
    const start = answer.indexOf(quote);
    if (!quote || start < 0) continue;
    const end = start + quote.length;
    if (ranges.some(([a, b]) => start < b && end > a)) continue;
    ranges.push([start, end]);
  }
  ranges.sort((x, y) => x[0] - y[0]);
  const segments: Segment[] = [];
  let cursor = 0;
  for (const [start, end] of ranges) {
    if (start > cursor) segments.push({ text: answer.slice(cursor, start), mark: false });
    segments.push({ text: answer.slice(start, end), mark: true });
    cursor = end;
  }
  if (cursor < answer.length || segments.length === 0) {
    segments.push({ text: answer.slice(cursor), mark: false });
  }
  return segments;
}

export function durationMinutes(startedAt?: string | null, endedAt?: string | null): number | null {
  if (!startedAt || !endedAt) return null;
  return Math.round((Date.parse(endedAt) - Date.parse(startedAt)) / 60_000);
}

/** Speeches in the transcript: every MIA turn plus every answer. */
export function speechCount(turns: { answer_text: string | null }[]): number {
  return turns.length + turns.filter((t) => t.answer_text).length;
}
