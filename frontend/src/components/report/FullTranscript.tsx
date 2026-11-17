import { Fragment } from "react";
import { ChevronRight } from "lucide-react";
import { QuestionDivider } from "@/components/interview/QuestionDivider";
import { TranscriptTurn } from "@/components/interview/TranscriptTurn";
import { questionNumbers } from "@/lib/interview";
import { speechCount } from "@/lib/report";
import type { Persona, PublicTurn } from "@/lib/types";

type FullTranscriptProps = { turns: PublicTurn[]; persona: Persona };

/** Closed `<details>` with the whole conversation, same look as the Interview (6.6, 6.8). */
export function FullTranscript({ turns, persona }: FullTranscriptProps) {
  const numbers = questionNumbers(turns);
  return (
    <details className="group">
      <summary className="flex cursor-pointer list-none items-center gap-2 text-body text-foreground">
        <ChevronRight className="size-4 transition-transform group-open:rotate-90" aria-hidden="true" />
        {`Mostrar transcrição completa (${speechCount(turns)} falas)`}
      </summary>
      <div className="mt-6 flex flex-col gap-8">
        {turns.map((t, i) => (
          <Fragment key={t.turn_no}>
            {i > 0 && t.question_id !== turns[i - 1].question_id && (
              <QuestionDivider n={numbers.get(t.question_id) ?? i + 1} />
            )}
            <TranscriptTurn variant="mia" persona={persona} text={t.interviewer_text} />
            {t.answer_text && <TranscriptTurn variant="candidate" persona={persona} text={t.answer_text} />}
          </Fragment>
        ))}
      </div>
    </details>
  );
}
