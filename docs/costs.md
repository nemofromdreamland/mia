# Costs

Model cost is a product metric in MIA: every call logs its tokens and an estimated cost, computed
from the prices in [`config/models.yaml`](../config/models.yaml). The numbers below come from
those logs, through `uv run python scripts/doc_numbers.py` and the tables in
[`results/`](../results/).

## Prices used

USD per million tokens, standard on-demand rate, us-east-1. Sources and check dates are in the
comments of `config/models.yaml`.

| Model | Input | Output | Used for |
| --- | --- | --- | --- |
| Claude Haiku 4.5 (Bedrock, `us.` profile) | 1.10 | 5.50 | Every production prompt |
| Mistral Large 3 (Bedrock) | 0.50 | 1.50 | Baseline comparison |
| Amazon Nova Pro (Bedrock) | 0.80 | 3.20 | Baseline comparison |
| `gpt-oss-120b` (Groq, free tier) | 0.15 | 0.60 | Synthetic eval answers |
| Amazon Nova 2 Sonic (Bedrock) | *not confirmed* | *not confirmed* | Voice |

For free tiers, the table keeps the published **paid** rate, so cost comparisons between models
stay fair.

## Production (AWS demo, 2026-11-17)

| Metric | Value |
| --- | --- |
| Text model calls | 456 (0 errors) |
| Text cost, whole day | US$ 1.1152 |
| Completed text interviews | 19 |
| **Text cost per completed interview** | **US$ 0.0587** |
| Voice sessions | 11 |
| Voice tokens per session, median (input / output) | 1,331 / 1,167 |

The per-interview figure divides every text call of the day by the number of reports, so the
cost of abandoned sessions and smoke tests is included. Read it as an upper bound. Source:
[`results/production_summary.md`](../results/production_summary.md).

**The voice cost is not stated.** The Nova 2 Sonic rate in `config/models.yaml` was never
confirmed against the official price page, so only token counts are published.

## Evaluations

| Experiment | Calls | Cost (USD) | Source |
| --- | --- | --- | --- |
| Baseline v1, judge (set A), Claude Haiku 4.5 | 70 | 0.2454 | `results/baseline_v1.md` |
| Baseline v1, judge (set A), Mistral Large 3 | 70 | 0.0692 | `results/baseline_v1.md` |
| Baseline v1, judge (set A), Nova Pro | 70 | 0.1178 | `results/baseline_v1.md` |
| Promptfoo set A, judge on Haiku (70 items) | 279 | 0.9837 | `results/promptfoo_set_a.md` |
| Robustness set D, without / with guardrail | 54 / 49 | 0.2284 / 0.1590 | `results/robustez_v1.md` |

One judge call on Haiku costs about **US$ 0.0035** (v1) to **0.0038** (v2).

## What keeps the bill small

- **Nothing billed while idle:** AgentCore, Lambda, on-demand DynamoDB, S3 and CloudFront. No load
  balancer, NAT gateway or instance.
- **Zero-cost session start:** screening and plans are generated once, offline.
- **Caps:** 100 sessions per day in total, 5 per visitor, 30 turns and 45 minutes per session,
  API Gateway throttling, and AWS Budget alerts at 50%, 80% and 100%.
- **Short outputs:** the interviewer is limited to 250 output tokens per line.
- **Cached evals:** Promptfoo caches identical calls; CI replays recorded judge answers instead of
  calling a model.

AWS infrastructure (API Gateway, Lambda, AgentCore, storage) ran on the account's Free Plan
credits and is not broken down here.
