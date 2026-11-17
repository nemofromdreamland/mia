# ADR 0006: No login; an anonymous visitor id plus quotas

- **Status:** accepted
- **Sources:** [spec 3.4](../../specs/3.4-visitor-quotas.md), `docs/TRD.md` (identification,
  security), `src/mia/api/visitor.py`, `src/mia/quotas.py`

## Context

Recruiters should be able to try the demo in seconds. A login would add friction and store
personal data, and an open endpoint on paid models needs a cost ceiling.

## Decision

The browser creates a random UUID v4, keeps it in `localStorage` and sends it as `X-Visitor-Id`.
The backend validates it and never reads the visitor from the request body; every session
operation filters by it. Before a session is created, `quotas.py` checks the kill switch
(item `config/demo` in the `mia-meta` table), 100 sessions per day globally and 5 per visitor per day. API Gateway adds
throttling.

## Consequences

- No friction, and no personal data stored about the visitor.
- The id can be forged to dodge the per-visitor quota. This is accepted: the data is anonymous
  and the global quota still caps the cost.
- Clearing the browser loses access to past sessions.
- The recruiter screen never shows `visitor_id`; candidates appear as "Candidate N".
