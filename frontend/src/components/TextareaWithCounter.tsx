import { forwardRef, useId, type ComponentProps } from "react";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

type TextareaWithCounterProps = Omit<ComponentProps<"textarea">, "value" | "maxLength"> & {
  value: string;
  maxLength: number;
  warnAt: number;
  minRows: number;
  maxRows: number;
};

const COUNT = new Intl.NumberFormat("pt-BR");

/** Design section 5.2: counter outside the box; grows from `minRows` to `maxRows`, then scrolls. */
export const TextareaWithCounter = forwardRef<HTMLTextAreaElement, TextareaWithCounterProps>(
  function TextareaWithCounter({ value, maxLength, warnAt, minRows, maxRows, className, ...props }, ref) {
    const limitId = useId();
    const lines = value.split("\n").length;
    const rows = Math.min(maxRows, Math.max(minRows, lines));
    const atLimit = value.length >= maxLength;
    const near = value.length >= warnAt;
    const describedBy = [props["aria-describedby"], atLimit ? limitId : undefined].filter(Boolean).join(" ");
    return (
      <div className="flex flex-col gap-1">
        <Textarea
          ref={ref}
          {...props}
          value={value}
          maxLength={maxLength}
          rows={rows}
          aria-describedby={describedBy || undefined}
          className={cn("field-sizing-fixed min-h-0 resize-none text-answer md:text-answer", className)}
        />
        <div className="flex justify-end gap-3 text-small">
          {atLimit && (
            <span id={limitId} className="text-danger">
              {`Limite de ${COUNT.format(maxLength)} caracteres.`}
            </span>
          )}
          <span
            className={cn(
              "font-mono tabular-nums",
              atLimit ? "text-danger" : near ? "text-warning" : "text-muted-foreground",
            )}
          >
            {`${COUNT.format(value.length)} / ${COUNT.format(maxLength)}`}
          </span>
        </div>
      </div>
    );
  },
);
