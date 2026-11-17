import { MiaMark } from "@/components/MiaMark";
import { interviewName } from "@/lib/labels";
import type { Persona } from "@/lib/types";

type SpeakerLabelProps = { speaker: "mia" | "candidate"; persona: Persona; followUp?: boolean };

/** Design section 5.8: `label` above each speech. */
export function SpeakerLabel({ speaker, persona, followUp = false }: SpeakerLabelProps) {
  if (speaker === "candidate") {
    return <p className="label text-muted-foreground">Você</p>;
  }
  return (
    <p className="flex items-center gap-2">
      <MiaMark size={20} />
      <span className="label text-mia">{`MIA · ${interviewName(persona)}`}</span>
      {followUp && <span className="label text-muted-foreground">Aprofundamento</span>}
    </p>
  );
}
