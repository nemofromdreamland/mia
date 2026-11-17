import { useId } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatScore } from "@/lib/format";
import { chartPoints, chartSummary, type Point } from "@/lib/history";
import { interviewName } from "@/lib/labels";
import type { Persona, Session } from "@/lib/types";

// Chart colors are fixed hex values by design (Design 9.2); Recharts needs literals.
const MIA = "#8CC7A6";
const BG = "#161513";
const GRID = "#2E2B27";
const AXIS = "#A8A196";
const CURSOR = "#403C36";
type DotProps = { cx?: number; cy?: number; payload?: Point; active?: boolean };

function Marker({ cx = 0, cy = 0, payload, active }: DotProps) {
  const size = active ? 12 : 10;
  const fill = active ? MIA : BG;
  const r = size / 2;
  const common = { fill, stroke: MIA, strokeWidth: 2 };
  if (payload?.persona === "technical") {
    return <rect x={cx - r} y={cy - r} width={size} height={size} {...common} />;
  }
  if (payload?.persona === "manager") {
    return <polygon points={`${cx},${cy - r} ${cx + r},${cy + r} ${cx - r},${cy + r}`} {...common} />;
  }
  return <circle cx={cx} cy={cy} r={r} {...common} />;
}

function ChartTooltip({ active, payload }: { active?: boolean; payload?: { payload: Point }[] }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="rounded-md border border-border-strong bg-surface-raised px-3 py-2 text-small">
      <div className="font-medium">{p.title}</div>
      <div className="text-muted-foreground">
        {interviewName(p.persona)} · {p.date}
      </div>
      <div>Nota geral {formatScore(p.score)}</div>
    </div>
  );
}

const LEGEND: { persona: Persona; shape: string }[] = [
  { persona: "hr", shape: "●" },
  { persona: "technical", shape: "■" },
  { persona: "manager", shape: "▲" },
];

/** Design section 9.2: overall score of completed sessions, shape = persona. */
export function EvolutionChart({ sessions }: { sessions: Session[] }) {
  const summaryId = useId();
  const points = chartPoints(sessions);
  const tick = { fill: AXIS, fontFamily: "IBM Plex Mono", fontSize: 12 };
  return (
    <figure aria-describedby={summaryId} className="rounded-lg border border-border bg-card p-4">
      <figcaption className="label mb-4 text-muted-foreground">Evolução da nota geral</figcaption>
      <p id={summaryId} className="sr-only">
        {chartSummary(points)}
      </p>
      <div className="h-[200px] md:h-[240px]" aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis dataKey="label" axisLine={false} tickLine={false} tick={tick} />
            <YAxis domain={[1, 5]} ticks={[1, 2, 3, 4, 5]} width={24} axisLine={false} tickLine={false} tick={tick} />
            <Tooltip content={<ChartTooltip />} cursor={{ stroke: CURSOR, strokeWidth: 1 }} />
            <Line
              type="linear"
              dataKey="score"
              stroke={MIA}
              strokeWidth={2}
              isAnimationActive={false}
              dot={<Marker />}
              activeDot={<Marker active />}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <ul className="mt-3 flex flex-wrap gap-4 text-small text-muted-foreground">
        {LEGEND.map((l) => (
          <li key={l.persona}>
            <span aria-hidden="true">{l.shape}</span> {interviewName(l.persona)}
          </li>
        ))}
      </ul>
    </figure>
  );
}
