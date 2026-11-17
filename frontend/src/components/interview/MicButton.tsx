import { Mic, MicOff } from "lucide-react";
import { cn } from "@/lib/utils";

type MicButtonProps = { muted: boolean; disabled: boolean; onToggle: () => void };

/** Design section 8: circular 56 px, 1 px border, 24 px icon, aria-pressed = muted. */
export function MicButton({ muted, disabled, onToggle }: MicButtonProps) {
  const label = disabled ? "Microfone indisponível" : muted ? "Ativar microfone" : "Silenciar microfone";
  return (
    <button
      type="button"
      aria-label={label}
      aria-pressed={muted}
      aria-disabled={disabled || undefined}
      onClick={() => !disabled && onToggle()}
      className={cn(
        "flex size-14 shrink-0 items-center justify-center rounded-full border",
        disabled
          ? "border-border-strong text-muted-foreground"
          : muted
            ? "border-danger bg-danger-muted text-danger"
            : "border-mia bg-mia-muted text-mia",
      )}
    >
      {muted && !disabled ? (
        <MicOff className="size-6" aria-hidden="true" />
      ) : (
        <Mic className="size-6" aria-hidden="true" />
      )}
    </button>
  );
}
