import { forwardRef, useId, useState, type KeyboardEvent } from "react";
import { Loader2 } from "lucide-react";
import { TextareaWithCounter } from "@/components/TextareaWithCounter";
import { Button } from "@/components/ui/button";

type AnswerComposerProps = {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  sending: boolean;
  disabled?: boolean;
  error?: string | null;
};

const IS_MAC = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);

/** Design section 5.13: Enter breaks the line, Ctrl/⌘ + Enter sends. */
export const AnswerComposer = forwardRef<HTMLTextAreaElement, AnswerComposerProps>(function AnswerComposer(
  { value, onChange, onSend, sending, disabled = false, error },
  ref,
) {
  const [blank, setBlank] = useState(false);
  const helpId = useId();
  const message = error ?? (blank ? "Escreva uma resposta antes de enviar." : null);

  function trySend() {
    if (sending || disabled) return;
    if (!value.trim()) return setBlank(true);
    setBlank(false);
    onSend();
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      trySend();
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <TextareaWithCounter
        ref={ref}
        data-testid="answer-input"
        aria-label="Sua resposta"
        placeholder="Responda como responderia na entrevista"
        value={value}
        maxLength={4000}
        warnAt={3600}
        minRows={3}
        maxRows={10}
        disabled={disabled}
        aria-invalid={error ? true : undefined}
        aria-describedby={message ? helpId : undefined}
        onChange={(e) => {
          setBlank(false);
          onChange(e.target.value);
        }}
        onKeyDown={onKeyDown}
      />
      {message && (
        <p id={helpId} className={error ? "text-small text-danger" : "text-small text-muted-foreground"}>
          {message}
        </p>
      )}
      <div className="flex items-center justify-between gap-3">
        <span className="hidden text-small text-muted-foreground md:inline">
          {IS_MAC ? "⌘ + Enter para enviar" : "Ctrl + Enter para enviar"}
        </span>
        <Button
          data-testid="send-answer"
          className="ml-auto"
          aria-disabled={sending || disabled}
          aria-busy={sending}
          onClick={trySend}
        >
          {sending && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
          {sending ? "Enviando…" : "Enviar"}
        </Button>
      </div>
    </div>
  );
});
