import { fitLabel } from "@/lib/labels";

/** Design section 5.15: one color for every value; the label carries the meaning. */
export function FitScore({ score }: { score: number }) {
  const value = Math.min(100, Math.max(0, Math.round(score)));
  const label = fitLabel(value);
  return (
    <div className="flex flex-col gap-2">
      <p className="flex items-baseline gap-1">
        <span className="font-serif text-display">{value}</span>
        <span className="text-h2 text-muted-foreground">/100</span>
      </p>
      <div
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={value}
        aria-valuetext={`${value} de 100, ${label.toLowerCase()}`}
        aria-label="Aderência à vaga"
        className="relative h-1 w-[240px] max-w-full bg-border-strong"
      >
        <div className="h-full bg-mia" style={{ width: `${value}%` }} />
        {[40, 70].map((mark) => (
          <span
            key={mark}
            aria-hidden="true"
            className="absolute -top-0.5 h-2 w-px bg-foreground-soft"
            style={{ left: `${mark}%` }}
          />
        ))}
      </div>
      <p className="text-small text-foreground-soft">{label}</p>
    </div>
  );
}
