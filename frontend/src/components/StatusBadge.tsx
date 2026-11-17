import { statusLabel } from "@/lib/labels";
import type { SessionStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const STYLES: Record<SessionStatus, string> = {
  preparing: "text-muted-foreground border-border-strong",
  ready: "text-foreground border-border-strong",
  in_progress: "text-mia border-mia/40",
  scoring: "text-muted-foreground border-border-strong",
  completed: "text-muted-foreground border-border",
  failed: "text-danger border-danger/40",
  abandoned: "text-muted-foreground border-border",
};

/** Design section 5.6. */
export function StatusBadge({ status }: { status: SessionStatus }) {
  return (
    <span
      className={cn(
        "label inline-flex items-center gap-2 rounded-md border px-2 py-1 whitespace-nowrap",
        STYLES[status],
      )}
    >
      {status === "in_progress" && (
        <span className="size-1.5 rounded-full bg-mia" aria-hidden="true" />
      )}
      {statusLabel(status)}
    </span>
  );
}
