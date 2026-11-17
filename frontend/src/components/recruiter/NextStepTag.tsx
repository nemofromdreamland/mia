import { nextStepLabel } from "@/lib/labels";
import type { NextStep } from "@/lib/types";

/** Design 6.8: neutral chip, no quality color (section 2.3). */
export function NextStepTag({ step }: { step: NextStep }) {
  return (
    <span
      data-testid="next-step"
      className="label inline-block rounded-md border border-border-strong px-2 py-1 text-foreground"
    >
      {nextStepLabel(step)}
    </span>
  );
}
