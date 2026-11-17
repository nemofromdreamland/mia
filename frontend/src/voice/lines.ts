import type { LiveLine } from "./useVoice";

/** Voice lines not yet in `turns`. Sonic re-speaks the last saved turn as the opening, maybe
 * split into sentences: hide those lines until the candidate first speaks. */
export function liveLines(lines: LiveLine[], lastText: string | undefined): LiveLine[] {
  const firstCandidate = lines.findIndex((l) => l.role === "candidate");
  return lines.filter((l, i) => {
    const beforeCandidate = firstCandidate === -1 || i < firstCandidate;
    const text = l.text.trim();
    return !(beforeCandidate && l.role === "interviewer" && text && lastText?.includes(text));
  });
}
