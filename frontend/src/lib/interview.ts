// Pure helpers for the interview transcript and clock (Design 6.5 and 13).

/** From 40:00 on, the clock warns that 5 minutes are left. */
export const WARNING_AT_SECONDS = 40 * 60;

type HasQuestion = { question_id: string };

/** "Pergunta N": distinct `question_id`s; a follow-up keeps the counter still. */
export function countQuestions(turns: HasQuestion[]): number {
  return new Set(turns.map((t) => t.question_id)).size;
}

/** Position (1-based) of each `question_id` in order of appearance. */
export function questionNumbers(turns: HasQuestion[]): Map<string, number> {
  const numbers = new Map<string, number>();
  for (const t of turns) {
    if (!numbers.has(t.question_id)) numbers.set(t.question_id, numbers.size + 1);
  }
  return numbers;
}

export function elapsedSeconds(startedAt: string, now: number): number {
  return Math.max(0, Math.floor((now - Date.parse(startedAt)) / 1000));
}
