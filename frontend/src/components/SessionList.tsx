import { useState } from "react";
import { Loader2, Trash2 } from "lucide-react";
import { Link } from "react-router";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { RubricScore } from "@/components/RubricScore";
import { StatusBadge } from "@/components/StatusBadge";
import { Button, buttonVariants } from "@/components/ui/button";
import { formatDateShort } from "@/lib/format";
import { personaColumn } from "@/lib/labels";
import type { CaseSummary, Session, SessionStatus } from "@/lib/types";
import { sessionTitle } from "@/lib/history";
import { cn } from "@/lib/utils";

type SessionListProps = {
  sessions: Session[];
  cases: CaseSummary[];
  onDelete: (session: Session) => Promise<void>;
};

type Action = { label: string; to: string; primary: boolean; testId?: string };

function mainAction(s: Session): Action | null {
  const base = `/sessao/${s.session_id}`;
  const actions: Partial<Record<SessionStatus, Action>> = {
    preparing: { label: "Ver preparo", to: `${base}/preparo`, primary: false },
    ready: { label: "Começar", to: `${base}/preparo`, primary: false },
    in_progress: { label: "Continuar", to: `${base}/entrevista`, primary: true },
    scoring: { label: "Ver feedback", to: `${base}/relatorio`, primary: false, testId: "view-feedback" },
    completed: { label: "Ver feedback", to: `${base}/relatorio`, primary: false, testId: "view-feedback" },
  };
  return actions[s.status] ?? null;
}

/** Design section 5.7: table on desktop, stacked cards on mobile (same DOM). */
export function SessionList({ sessions, cases, onDelete }: SessionListProps) {
  const [pending, setPending] = useState<Session | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  async function confirmDelete() {
    const target = pending;
    setPending(null);
    if (!target) return;
    setDeleting(target.session_id);
    try {
      await onDelete(target);
    } finally {
      setDeleting(null);
    }
  }

  return (
    <>
      <table className="w-full text-body">
        <thead className="hidden md:table-header-group">
          <tr className="label text-left text-muted-foreground">
            <th className="py-2 font-medium">Caso</th>
            <th className="w-[160px] py-2 font-medium">Entrevista</th>
            <th className="w-[120px] py-2 font-medium">Data</th>
            <th className="w-[140px] py-2 font-medium">Nota</th>
            <th className="w-[150px] py-2 font-medium">Status</th>
            <th className="w-[200px] py-2 font-medium">
              <span className="sr-only">Ações</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {sessions.map((s) => {
            const title = sessionTitle(s, cases);
            const action = mainAction(s);
            const canDelete = s.status !== "scoring";
            return (
              <tr
                key={s.session_id}
                data-testid="session-row"
                className="flex flex-col gap-2 border-b border-border py-4 transition-colors duration-150 ease-out hover:bg-hover md:table-row md:h-14 md:py-0"
              >
                <td className="truncate font-medium md:max-w-0 md:pr-4">{title}</td>
                <td className="inline text-small text-muted-foreground md:table-cell md:text-body md:text-foreground">
                  {personaColumn(s.persona)}
                </td>
                <td className="inline font-mono text-small text-muted-foreground tabular-nums md:table-cell md:text-body md:text-foreground">
                  {formatDateShort(s.created_at)}
                </td>
                <td className="md:table-cell">
                  {s.overall_score === null ? "—" : <RubricScore score={s.overall_score} />}
                </td>
                <td className="md:table-cell">
                  <StatusBadge status={s.status} />
                </td>
                <td className="md:table-cell">
                  <div className="flex items-center justify-end gap-2">
                    {action && (
                      <Link
                        to={action.to}
                        data-testid={action.testId}
                        className={cn(
                          buttonVariants({ variant: action.primary ? "default" : "outline", size: "sm" }),
                          "flex-1 md:flex-none",
                        )}
                      >
                        {action.label}
                      </Link>
                    )}
                    {canDelete &&
                      (deleting === s.session_id ? (
                        <Loader2 className="size-4 animate-spin" aria-label="Apagando" />
                      ) : (
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`Apagar simulação ${title}`}
                          onClick={() => setPending(s)}
                        >
                          <Trash2 aria-hidden="true" />
                        </Button>
                      ))}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <ConfirmDialog
        open={pending !== null}
        title="Apagar esta simulação?"
        body="O feedback desta simulação também será apagado, inclusive da tela do recrutador. Isso não pode ser desfeito."
        confirmLabel="Apagar"
        onConfirm={confirmDelete}
        onOpenChange={(open) => !open && setPending(null)}
      />
    </>
  );
}
