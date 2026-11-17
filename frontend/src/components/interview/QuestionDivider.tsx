/** Design section 5.10: line with "PERGUNTA N" before each new question. */
export function QuestionDivider({ n }: { n: number }) {
  return (
    <div className="mt-8 flex items-center gap-3" role="separator" aria-label={`Pergunta ${n}`}>
      <span className="label text-muted-foreground">{`Pergunta ${n}`}</span>
      <span className="h-px flex-1 bg-border" aria-hidden="true" />
    </div>
  );
}
