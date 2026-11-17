import { Link } from "react-router";
import { RubricScore } from "@/components/RubricScore";
import { buttonVariants } from "@/components/ui/button";
import { formatDateShort, formatScore } from "@/lib/format";
import { formatDelta } from "@/lib/labels";
import type { RecruiterCandidateRow } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Design 6.7: a table row on desktop, a card below `md`. Renders field by field,
 * so nothing but the anonymous row data can reach the screen.
 */
export function RecruiterRow({ row }: { row: RecruiterCandidateRow }) {
  const delta = row.delta_vs_case_avg;
  return (
    <tr
      data-testid="recruiter-row"
      className="flex flex-col gap-2 border-b border-border py-4 md:table-row md:h-14 md:py-0"
    >
      <td className="font-mono md:pr-4">
        {`Candidato ${row.candidate_no}`}
        <span className="font-mono text-muted-foreground md:hidden">{` · ${formatDateShort(row.ended_at)}`}</span>
      </td>
      <td className="hidden font-mono tabular-nums md:table-cell">{formatDateShort(row.ended_at)}</td>
      <td className="md:table-cell">
        <span className="flex items-center gap-3">
          <RubricScore score={row.overall_score} showNumber={false} />
          <span className="font-mono tabular-nums">{formatScore(row.overall_score)}</span>
          <span className="font-mono text-foreground tabular-nums md:hidden">
            {delta === null ? "—" : `${formatDelta(delta)} acima da média`}
          </span>
        </span>
      </td>
      <td className="hidden font-mono text-foreground tabular-nums md:table-cell">
        {delta === null ? "—" : formatDelta(delta)}
      </td>
      <td className="md:max-w-0 md:pr-4">
        <p className="line-clamp-2 text-small text-foreground-soft md:line-clamp-none md:truncate">{row.headline}</p>
      </td>
      <td className="md:table-cell md:text-right">
        <Link
          to={`/recrutador/${row.session_id}`}
          className={cn(buttonVariants({ variant: "outline" }), "w-full md:w-auto")}
        >
          Ver candidato
        </Link>
      </td>
    </tr>
  );
}
