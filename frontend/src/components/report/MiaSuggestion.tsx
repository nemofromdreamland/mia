/** Design section 5.17: left border `mia`, never highlighted. */
export function MiaSuggestion({ text }: { text: string }) {
  return (
    <div className="flex flex-col gap-1 border-l-2 border-mia pl-4">
      <p className="label text-mia">Uma resposta mais forte</p>
      <p className="text-answer text-foreground">{text}</p>
    </div>
  );
}
