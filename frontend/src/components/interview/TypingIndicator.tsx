import { MiaMark } from "@/components/MiaMark";
import { Button } from "@/components/ui/button";

type TypingIndicatorProps = { slow: boolean; onResend: () => void };

/** Design section 5.11: sits where the next MIA speech will appear. */
export function TypingIndicator({ slow, onResend }: TypingIndicatorProps) {
  return (
    <div role="status" className="flex flex-col gap-1 text-small text-muted-foreground">
      <p className="flex items-center gap-2">
        <MiaMark size={16} state="thinking" />
        MIA está escrevendo…
      </p>
      {slow && (
        <p className="flex items-center gap-2">
          Está demorando mais que o normal.
          <Button variant="link" size="sm" className="h-auto p-0" onClick={onResend}>
            Reenviar resposta
          </Button>
        </p>
      )}
    </div>
  );
}
