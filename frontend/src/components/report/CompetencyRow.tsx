import { RubricScore } from "@/components/RubricScore";
import { formatScore } from "@/lib/format";
import type { CompetencyScore } from "@/lib/types";

type CompetencyRowProps = { item: CompetencyScore; before?: number };

/** Design section 5.20. Scores always with one decimal ("4,0"). */
export function CompetencyRow({ item, before }: CompetencyRowProps) {
  return (
    <div className="flex flex-col gap-2 border-b border-border pb-6 last:border-b-0 last:pb-0">
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <h3 className="text-h3">{item.competency}</h3>
        <div className="flex items-center gap-3">
          <RubricScore score={item.score} showNumber={false} />
          <span className="font-mono tabular-nums">{formatScore(item.score)}</span>
          {before !== undefined && (
            <span className="text-small text-muted-foreground">{`antes ${formatScore(before)}`}</span>
          )}
        </div>
      </div>
      <p className="text-body text-foreground-soft">{item.summary}</p>
    </div>
  );
}
