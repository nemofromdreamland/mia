type EvidenceQuoteProps = {
  label: string;
  quote: string;
  /** Text the quote must come from; when given, a quote not found in it is dropped. */
  source?: string;
  verified?: boolean | null;
};

/** Design section 5.16 (block): literal excerpt with highlighter, or nothing. */
export function EvidenceQuote({ label, quote, source, verified }: EvidenceQuoteProps) {
  if (verified === false || !quote) return null;
  if (source !== undefined && !source.includes(quote)) return null;
  return (
    <figure className="flex flex-col gap-1">
      <figcaption className="label text-muted-foreground">{label}</figcaption>
      <blockquote className="text-body">
        <mark>{`“${quote}”`}</mark>
      </blockquote>
    </figure>
  );
}
