# ADR 0002: Claude Haiku 4.5 on Bedrock is the default model

- **Status:** accepted
- **Sources:** `specs/0.6-smoke-providers.md`, `specs/2.7-baseline-v1.md`, `results/baseline_v1.md`, `config/models.yaml`

## Context

Every production prompt needs one model: the interviewer runs in the conversation loop, where
latency matters; the judge decides the scores, where agreement with a human matters. Gate 0
(ADR 0001) confirmed Claude, Nova and Mistral on Bedrock, Gemini and Groq. Gemini 3.8 Flash took
19 to 107 s per call with default reasoning.

## Decision

Claude Haiku 4.5 (`us.` inference profile on Bedrock) is the route for every production prompt
in `config/models.yaml` (`prompt_models`). Groq `gpt-oss-120b` only generates synthetic eval
answers. Gemini is used only in provider comparisons, never as the default.

## Consequences

- Best judge agreement in the baseline: kappa 0.61 on test, against 0.53 for Mistral Large 3 and
  0.43 for Nova Pro, with a stable p95 latency of 4.8 s.
- About 3.5 times the judge cost per call of Mistral (US$ 0.00351 against 0.00099). At a few cents
  per interview this was accepted.
- The judge never grades answers written by its own model family.
- Moving off Bedrock is a config change (ADR 0003), not a rewrite.
