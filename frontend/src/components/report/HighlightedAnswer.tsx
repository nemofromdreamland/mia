import { highlight } from "@/lib/report";

/** Design section 5.16 (inline): <mark> on the verified quotes inside the answer. */
export function HighlightedAnswer({ answer, quotes }: { answer: string; quotes: string[] }) {
  return (
    <>
      {highlight(answer, quotes).map((segment, i) =>
        segment.mark ? <mark key={i}>{segment.text}</mark> : <span key={i}>{segment.text}</span>,
      )}
    </>
  );
}
