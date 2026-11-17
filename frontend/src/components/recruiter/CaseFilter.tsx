import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { CaseSummary } from "@/lib/types";

type CaseFilterProps = {
  cases: CaseSummary[];
  value: string | null;
  onChange: (caseId: string | null) => void;
};

const ALL = "all";

/** Design 6.7: 280 px select ("Todos os casos" + the cases), full width on phones. */
export function CaseFilter({ cases, value, onChange }: CaseFilterProps) {
  return (
    <Select value={value ?? ALL} onValueChange={(v) => onChange(v === ALL ? null : v)}>
      <SelectTrigger data-testid="case-filter" aria-label="Filtrar por caso" className="w-full md:w-[280px]">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL}>Todos os casos</SelectItem>
        {cases.map((c) => (
          <SelectItem key={c.case_id} value={c.case_id}>
            {c.title}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
