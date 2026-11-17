import type { ReactNode } from "react";
import { CircleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type InlineNoticeProps = {
  variant: "warning" | "danger" | "neutral";
  children: ReactNode;
  action?: { label: string; onClick: () => void };
  className?: string;
};

const VARIANTS = {
  warning: "bg-warning-muted text-warning",
  danger: "bg-danger-muted text-danger",
  neutral: "bg-card text-foreground-soft",
};

/** Design section 5.26. */
export function InlineNotice({ variant, children, action, className }: InlineNoticeProps) {
  return (
    <div
      role={variant === "neutral" ? "note" : "alert"}
      className={cn("flex items-start gap-3 rounded-md px-4 py-3 text-small", VARIANTS[variant], className)}
    >
      <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <div className="flex-1">{children}</div>
      {action && (
        <Button variant="link" size="sm" className="h-auto p-0" onClick={action.onClick}>
          {action.label}
        </Button>
      )}
    </div>
  );
}
