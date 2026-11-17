// Number and date formats from Design section 9.1 (pt-BR).

const SCORE = new Intl.NumberFormat("pt-BR", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});
const DATE_SHORT = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short" });
const DATE_LONG = new Intl.DateTimeFormat("pt-BR", { dateStyle: "long" });

export function formatScore(value: number): string {
  return SCORE.format(value);
}

export function formatAnswerScore(value: number): string {
  return `${value} de 5`;
}

export function formatFit(value: number): string {
  return `${Math.round(value)}/100`;
}

export function formatDateShort(iso: string): string {
  return DATE_SHORT.format(new Date(iso));
}

export function formatDateLong(iso: string): string {
  return DATE_LONG.format(new Date(iso));
}

export function formatMinutes(minutes: number): string {
  return `${Math.round(minutes)} min`;
}

export function formatClock(totalSeconds: number): string {
  const seconds = Math.max(0, Math.floor(totalSeconds));
  const mm = String(Math.floor(seconds / 60)).padStart(2, "0");
  const ss = String(seconds % 60).padStart(2, "0");
  return `${mm}:${ss}`;
}
