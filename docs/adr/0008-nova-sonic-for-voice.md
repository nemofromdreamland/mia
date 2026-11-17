# ADR 0008: Amazon Nova 2 Sonic for voice, sharing the text tools

- **Status:** accepted
- **Sources:** `specs/0.8-sonic-pt.md`, `specs/5-voice-demo.md`, `specs/5.6-voice-ux.md`, `results/production_summary.md`

## Context

Voice was the last, optional phase ("text first, voice last"). A cascade (speech-to-text, model,
text-to-speech) gives control over each step but adds latency and needs its own turn-taking.

## Decision

Use Nova 2 Sonic (speech-to-speech) through its native bidirectional protocol, adapted from the
official AWS sample rather than an experimental framework. Sonic talks and listens, while the
interview logic stays in the same code as text mode: the code stores the turn, scores it and
prepares the next line, and Sonic fetches that line through a `next_line` tool.

## Consequences

- Median time to first audio was 1.31 s (p90 1.49 s) over 11 production sessions.
- Portuguese quality was approved in a manual test at Gate 0.
- Sonic was unreliable at calling tools on its own and at reading text verbatim, so control stayed
  in code (ADR 0004).
- Voice cost is not stated: the Sonic price in `config/models.yaml` was never confirmed against
  the official price page. Only tokens per session are published.
- No audio is stored, only the transcript.
