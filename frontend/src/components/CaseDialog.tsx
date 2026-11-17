import { useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { InlineNotice } from "@/components/InlineNotice";
import { Button } from "@/components/ui/button";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ApiError, apiRequest } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { interviewName, levelText } from "@/lib/labels";
import type { CaseSummary, Mode, Session } from "@/lib/types";

function voiceEnabled(): boolean {
  return import.meta.env.VITE_VOICE_ENABLED === "true";
}

type CaseDialogProps = {
  item: CaseSummary | null;
  blocked: ApiError | null;
  onClose: () => void;
  onCreated: (session: Session) => void;
  onBlocked: (error: ApiError) => void;
};

const BLOCKING = new Set(["quota_exceeded", "demo_paused"]);

function blockedText(error: ApiError): string {
  // In the dialog the paused notice is the short one (Design 5.31).
  if (error.code === "demo_paused") return "A demo está pausada no momento.";
  return errorMessage(error, "case_dialog").text;
}

/** Design section 5.31. */
export function CaseDialog({ item, blocked, onClose, onCreated, onBlocked }: CaseDialogProps) {
  const [creating, setCreating] = useState(false);
  const [mode, setMode] = useState<Mode>("text");
  const showMode = voiceEnabled();

  async function start() {
    if (!item) return;
    setCreating(true);
    try {
      const session = await apiRequest<Session>("POST", "/sessions", {
        case_id: item.case_id,
        mode: showMode ? mode : "text",
      });
      onCreated(session);
    } catch (err) {
      const error = err instanceof ApiError ? err : new ApiError("internal", true, null);
      if (BLOCKING.has(error.code)) onBlocked(error);
      else toast.error(errorMessage(error, "case_dialog").text);
    } finally {
      setCreating(false);
    }
  }

  return (
    <Dialog open={item !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[520px]">
        {item && (
          <>
            <DialogHeader>
              <DialogTitle className="text-h2 font-medium">{item.title}</DialogTitle>
              <DialogDescription className="text-small text-muted-foreground">
                {item.company} · {levelText(item.level)} · {interviewName(item.persona)} · cerca de{" "}
                {item.estimated_minutes} min
              </DialogDescription>
            </DialogHeader>
            <Clamp label="A vaga" text={item.blurb} />
            <Clamp label="Você vai interpretar" text={item.candidate_blurb} soft />
            {showMode && (
              <section className="flex flex-col gap-2">
                <h3 id="mode-label" className="label text-muted-foreground">
                  Formato
                </h3>
                <ToggleGroup
                  type="single"
                  variant="outline"
                  aria-labelledby="mode-label"
                  value={mode}
                  onValueChange={(value) => value && setMode(value as Mode)}
                  className="w-full"
                >
                  <ToggleGroupItem value="text" data-testid="mode-text" className="flex-1">
                    Texto
                  </ToggleGroupItem>
                  <ToggleGroupItem value="voice" data-testid="mode-voice" className="flex-1">
                    Voz
                  </ToggleGroupItem>
                </ToggleGroup>
              </section>
            )}
            <p className="text-small text-muted-foreground">
              Respostas anônimas, visíveis ao recrutador da demo. Não use dados pessoais.
            </p>
            {blocked && <InlineNotice variant="warning">{blockedText(blocked)}</InlineNotice>}
            <DialogFooter>
              <Button variant="outline" onClick={onClose}>
                Cancelar
              </Button>
              <Button
                data-testid="start-case"
                onClick={start}
                disabled={creating || blocked !== null}
                aria-busy={creating}
              >
                {creating && <Loader2 className="animate-spin" aria-hidden="true" />}
                {creating ? "Criando…" : "Começar"}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

/** Spec 5.6: at most 2 lines, with "Ver mais" to expand. */
function Clamp({ label, text, soft = false }: { label: string; text: string; soft?: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <section className="flex flex-col gap-1">
      <h3 className="label text-muted-foreground">{label}</h3>
      <p className={`text-body ${soft ? "text-foreground-soft" : ""} ${open ? "" : "line-clamp-2"}`}>{text}</p>
      {text.length > 120 && (
        <Button variant="link" size="sm" className="h-auto self-start p-0" onClick={() => setOpen((o) => !o)}>
          {open ? "Ver menos" : "Ver mais"}
        </Button>
      )}
    </section>
  );
}
