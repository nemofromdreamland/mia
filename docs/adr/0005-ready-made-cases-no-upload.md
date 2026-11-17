# ADR 0005: The web demo uses 5 ready-made fictitious cases, no CV upload

- **Status:** accepted
- **Sources:** `docs/PRD.md`, `docs/CASES.md`, `scripts/build_cases.py`, `cases/`

## Context

A public demo without login that accepted CV uploads would receive real personal data, pay for a
screening and planning call per visitor, and expose the prompts to untrusted documents.

## Decision

The web offers 5 fictitious cases (CV + job). Their screening and interview plan are generated
offline by the same LangGraph prep graph the CLI uses, reviewed by hand, and committed under
`cases/` with a `version` that goes up whenever a fixture changes. The API has no upload route.
The CLI still accepts any fictitious CV and job.

## Consequences

- Creating a session never calls a model, which keeps the quota cheap and the start instant.
- No real CV ever reaches the models or the repository.
- Visitors cannot try their own CV on the web. The CLI covers that use for developers.
- Plans are reviewable in git like any other code.
