import { TranscriptTurn } from "@/components/interview/TranscriptTurn";
import { RubricScore } from "@/components/RubricScore";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { groupByQuestion, verifiedQuotes } from "@/lib/report";
import type { Persona, Turn } from "@/lib/types";
import { CriteriaList } from "./CriteriaList";
import { HighlightedAnswer } from "./HighlightedAnswer";

type AnswerByAnswerProps = { turns: Turn[]; persona: Persona };

/** Design section 6.6 "Resposta por resposta": closed accordion, one item per question. */
export function AnswerByAnswer({ turns, persona }: AnswerByAnswerProps) {
  return (
    <Accordion type="multiple" className="flex flex-col">
      {groupByQuestion(turns).map((group) => {
        const first = group.turns[0].score;
        return (
          <AccordionItem key={group.questionId} value={group.questionId}>
            <AccordionTrigger className="items-center text-body">
              <span className="flex flex-1 items-center justify-between gap-4">
                <span>{`Pergunta ${group.n}`}</span>
                {first && <RubricScore score={first.score} />}
              </span>
            </AccordionTrigger>
            <AccordionContent className="flex flex-col gap-8 pt-2 pb-6">
              {group.turns.map((turn, i) => (
                <TurnDetail key={turn.turn_no} turn={turn} persona={persona} showScore={i > 0} />
              ))}
            </AccordionContent>
          </AccordionItem>
        );
      })}
    </Accordion>
  );
}

type TurnDetailProps = { turn: Turn; persona: Persona; showScore: boolean };

function TurnDetail({ turn, persona, showScore }: TurnDetailProps) {
  const answer = turn.answer_text;
  const quotes = answer ? verifiedQuotes(answer, turn.score) : [];
  return (
    <div className="flex flex-col gap-4">
      <TranscriptTurn variant="mia" persona={persona} text={turn.interviewer_text} followUp={turn.is_follow_up} />
      {answer && (
        <TranscriptTurn variant="candidate" persona={persona} text={answer}>
          <HighlightedAnswer answer={answer} quotes={quotes} />
        </TranscriptTurn>
      )}
      {answer && turn.score && quotes.length === 0 && (
        <p className="text-small text-muted-foreground">Sem trecho destacado para esta resposta.</p>
      )}
      {answer && !turn.score && <p className="text-body text-muted-foreground">Esta resposta não foi avaliada.</p>}
      {turn.score && (
        <>
          {showScore && <RubricScore score={turn.score.score} />}
          <div className="flex flex-col gap-2">
            <p className="label text-muted-foreground">Critérios atendidos</p>
            <CriteriaList items={turn.score.criteria_met} />
          </div>
          <div className="flex flex-col gap-2">
            <p className="label text-muted-foreground">Por que essa nota</p>
            <p className="text-body text-foreground-soft">{turn.score.justification}</p>
          </div>
        </>
      )}
    </div>
  );
}
