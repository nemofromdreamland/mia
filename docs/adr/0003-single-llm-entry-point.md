# ADR 0003: `llm.py` is the only module that calls models

- **Status:** accepted
- **Sources:** [spec 0.5](../../specs/0.5-llm-minimal.md), `docs/TRD.md` (principles),
  `src/mia/llm.py`, `tests/test_prompt_models_guard.py`

## Context

The project compares providers (Bedrock, Groq, Gemini), validates every output and has to log
cost and latency for every call. If each module called a provider SDK, each would need its own
retry, validation and logging, and they would drift apart.

## Decision

Only `src/mia/llm.py` imports a provider SDK (LangChain `init_chat_model`). It resolves the model
from `config/models.yaml`, applies retries, validates the output against the Pydantic schema
named in the prompt YAML (with one repair attempt), and writes a `RunRecord` to `runs/*.jsonl`.
Prompts live in `prompts/<name>/v<N>.yaml` and are never edited after use.

## Consequences

- Switching provider is one line of config. A guard test fails if a prompt has no route.
- Every metric in `results/` can be recomputed from the run records, even after the AWS account
  closed.
- Provider-specific features need explicit, narrow exceptions: Guardrails pass through `llm.py`
  as a parameter, and the Sonic voice stream lives in `voice/sonic.py`.
