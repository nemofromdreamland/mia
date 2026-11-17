# ADR 0004: The model writes, the code decides

- **Status:** accepted
- **Sources:** `docs/TRD.md` (principles), `src/mia/interviewer.py`, `src/mia/judge.py`, `specs/5.6-voice-ux.md`

## Context

A mock interview needs predictable rules: how many follow-ups, time limits, when to move to the
next phase, and scores that trace back to what the candidate said. Models are good at wording and
unreliable at keeping counters or quoting exactly.

## Decision

State, limits and transitions are deterministic code. The interviewer prompt only writes the next
line. The follow-up cap (2 per question, 1 on the web), the turn and time limits, and the end of
the interview are enforced in `interviewer.py`. The judge's evidence quotes are checked literally
in code, and unverified quotes are dropped. In voice, the code decides when an answer ends.

## Consequences

- Behaviour is testable without a model: the 1,400+ tests run in CI with no model calls.
- Eval set B counts the effective action after the code's rules, not the raw model choice.
- Voice prompt v1 let Nova 2 Sonic call `submit_answer` on its own. It never did, and the
  interview stalled. v2 moved that decision to code and fixed the stall.
- Some flexibility is lost: the interviewer cannot dig deeper than the cap allows.
