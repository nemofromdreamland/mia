import { useId } from "react";
import { cn } from "@/lib/utils";

export type MiaState = "idle" | "thinking" | "speaking" | "listening";

type MiaMarkProps = {
  state?: MiaState;
  size?: 16 | 20 | 48 | 64 | 96;
  /** Se passado, o SVG vira role="img" com esse rótulo. Sem title, é decorativo. */
  title?: string;
  className?: string;
};

const THINKING_SMALL =
  "translate(5 -4) translate(50 44) scale(.82 1) translate(-50 -44)";

export function MiaMark({ state = "idle", size = 48, title, className }: MiaMarkProps) {
  const id = useId().replace(/:/g, "");
  const small = size <= 20;
  const a11y = title
    ? { role: "img" as const, "aria-label": title }
    : { "aria-hidden": true as const };

  return (
    <svg
      width={size}
      height={size}
      viewBox={small ? "14 12 72 72" : "0 0 100 100"}
      className={cn("mia-mark shrink-0", !small && `mia-${state}`, className)}
      {...a11y}
    >
      <defs>
        <radialGradient id={`${id}-b`} cx=".36" cy=".3" r=".8">
          <stop offset="0" stopColor="#C4E6D2" />
          <stop offset=".45" stopColor="#8CC7A6" />
          <stop offset="1" stopColor="#3F7358" />
        </radialGradient>
        <radialGradient id={`${id}-r`} cx=".5" cy="1.05" r=".55">
          <stop offset="0" stopColor="#8CC7A6" stopOpacity=".45" />
          <stop offset="1" stopColor="#8CC7A6" stopOpacity="0" />
        </radialGradient>
        <radialGradient id={`${id}-s`}>
          <stop offset="0" stopColor="#000" stopOpacity=".55" />
          <stop offset="1" stopColor="#000" stopOpacity="0" />
        </radialGradient>
      </defs>

      {!small && (
        <>
          <ellipse className="mia-floor" cx="50" cy="92" rx="36" ry="6" fill="none"
            stroke="#8CC7A6" strokeWidth={size < 64 ? 2.5 : 1.5} />
          <ellipse className="mia-shadow" cx="50" cy="92" rx="25" ry="4.5" fill={`url(#${id}-s)`} />
        </>
      )}

      <g className="mia-body">
        <circle cx="50" cy="48" r="36" fill={`url(#${id}-b)`} />
        <circle cx="50" cy="48" r="36" fill={`url(#${id}-r)`} />
        <g className="mia-eyes" transform={small && state === "thinking" ? THINKING_SMALL : undefined}>
          <rect x="37" y="37" width="7" height="15" rx="3.5" fill="#12211A" />
          <rect x="56" y="37" width="7" height="15" rx="3.5" fill="#12211A" />
        </g>
      </g>
    </svg>
  );
}
