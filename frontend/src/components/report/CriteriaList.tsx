import { Check } from "lucide-react";

/** Design section 5.18: only the criteria that were met (section 13). */
export function CriteriaList({ items }: { items: string[] }) {
  if (items.length === 0) {
    return <p className="text-body text-muted-foreground">Nenhum critério atendido nesta resposta.</p>;
  }
  return (
    <ul className="flex flex-col gap-2">
      {items.map((item) => (
        <li key={item} className="flex items-start gap-2 text-body">
          <Check className="mt-1 size-4 shrink-0 text-mia" aria-hidden="true" />
          {item}
        </li>
      ))}
    </ul>
  );
}
