import { formatAnswerScore, formatScore } from "@/lib/format";
import { rubricLabel } from "@/lib/labels";
import { cn } from "@/lib/utils";

type RubricScoreProps = {
  score: number;
  size?: "sm" | "md";
  showLabel?: boolean;
  /** Hide the number when it is already shown next to it (Report, Candidate). */
  showNumber?: boolean;
  className?: string;
};

/** Design section 5.14: five squares, number and optional label; no quality colors. */
export function RubricScore({
  score,
  size = "sm",
  showLabel = false,
  showNumber = true,
  className,
}: RubricScoreProps) {
  const filled = Math.round(score);
  const number = Number.isInteger(score) ? formatAnswerScore(score) : formatScore(score);
  const label = rubricLabel(score);
  return (
    <span
      role="img"
      aria-label={`Nota ${formatScore(score)} de 5: ${label.toLowerCase()}`}
      className={cn("inline-flex items-center gap-2", className)}
    >
      <span className="flex gap-1" aria-hidden="true">
        {[1, 2, 3, 4, 5].map((i) => (
          <span
            key={i}
            data-filled={i <= filled}
            className={cn(
              "rounded-sm",
              size === "sm" ? "size-2.5" : "size-3.5",
              i <= filled ? "bg-mia" : "bg-border-strong",
            )}
          />
        ))}
      </span>
      {showNumber && (
        <span aria-hidden="true" className="font-mono tabular-nums">
          {number}
        </span>
      )}
      {showLabel && (
        <span aria-hidden="true" className="text-small text-muted-foreground">
          {label}
        </span>
      )}
    </span>
  );
}
