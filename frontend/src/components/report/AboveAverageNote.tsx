import { Link } from "react-router";
import { ClipboardList } from "lucide-react";

/** Design section 5.33: neutral note, no celebration color. */
export function AboveAverageNote({ sessionId }: { sessionId: string }) {
  return (
    <div role="note" className="flex flex-wrap items-center gap-3 rounded-md bg-card px-4 py-3 text-small text-foreground-soft">
      <ClipboardList className="size-4 shrink-0" aria-hidden="true" />
      <span className="flex-1">Sua nota ficou acima da média deste caso.</span>
      <Link
        to={`/recrutador/${sessionId}`}
        data-testid="above-average-link"
        className="text-mia underline-offset-4 hover:text-mia-strong hover:underline"
      >
        Ver como o recrutador te vê
      </Link>
    </div>
  );
}
