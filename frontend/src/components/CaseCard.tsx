import { Clock } from "lucide-react";
import { levelLabel, personaLabel } from "@/lib/labels";
import type { CaseSummary } from "@/lib/types";

type CaseCardProps = { item: CaseSummary; onOpen: () => void };

/** Design section 5.30: the whole card is a button that opens the CaseDialog. */
export function CaseCard({ item, onOpen }: CaseCardProps) {
  return (
    <button
      type="button"
      aria-haspopup="dialog"
      data-testid={`case-card-${item.case_id}`}
      onClick={onOpen}
      className="flex min-h-[180px] flex-col gap-2 rounded-lg border border-border bg-card p-5 text-left transition-colors duration-150 ease-out hover:border-border-strong"
    >
      <span className="label text-muted-foreground">
        {personaLabel(item.persona)} · {levelLabel(item.level)}
      </span>
      <span className="text-h3 font-medium text-foreground">{item.title}</span>
      <span className="text-small text-muted-foreground">{item.company}</span>
      <span className="line-clamp-3 text-small text-foreground-soft">{item.candidate_blurb}</span>
      <span className="mt-auto flex items-center gap-2 pt-2 font-mono text-small text-muted-foreground tabular-nums">
        <Clock className="size-4" aria-hidden="true" />
        {item.estimated_minutes} min
        {item.completed_sessions > 0 && ` · ${item.completed_sessions} já fizeram`}
      </span>
    </button>
  );
}
