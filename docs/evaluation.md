# Evaluation

The judge decides the scores the visitor sees, so it was the first thing measured. Four fixed
eval sets run through **Promptfoo with a custom Python provider that calls the real code in
`src/mia/`**, never a copy of the prompts. Python assertions check each case, and
`evals/metrics.py` computes the aggregate metrics.

Every number on this page is printed by `uv run python scripts/doc_numbers.py`, which reads the
committed tables in [`results/`](../results/).

## Method

| Set | Data | What it measures |
| --- | --- | --- |
| **A. Judge** | 10 questions (6 technical, 4 behavioural) × 7 answers = **70 items**: 5 quality levels, 1 rambling answer, 1 paraphrase | Agreement with a human score: quadratic-weighted Cohen's kappa, MAE, % within ±1; verbosity bias; paraphrase consistency; share of verifiable quotes |
| **B. Tools** | **40** interview moments with the expected decision (follow up, next question, end) | Right action and right follow-up argument |
| **C. Plan** | The 5 web cases + 1 extra fictitious CV/job pair | Built as a dataset; plans are checked structurally in code (schema, literal CV quotes, coverage), not as a scored experiment |
| **D. Robustness** | **30** attacks: injection in the answer and in documents, off-topic, personal data, format variations | Share of attacks that changed a score or behaviour, with and without Bedrock Guardrails |

Rules that make the numbers trustworthy:

- **No grading of your own family.** A different model family (Groq, `gpt-oss-120b`) generated
  the synthetic answers; Claude judges them.
- **Blind human labels.** The project owner scored all 70 answers before seeing any judge score.
- **Dev/test split.** 49 dev and 21 test items, stratified by level. Prompts were tuned only on
  dev; every reported number is from **test**.
- **Fictitious data only.** Nothing real goes to free tiers or to git.
- **Regression in CI.** Recorded judge answers for set A replay on every pull request
  (`tests/test_eval_regression.py`), with no model calls.

## Results

### Choosing the judge model (baseline v1, test split)

| Model (Bedrock) | Kappa | Judge cost per call (USD) | p95 latency |
| --- | --- | --- | --- |
| **Claude Haiku 4.5** | **0.61** | 0.00351 | 4.8 s |
| Mistral Large 3 | 0.53 | 0.00099 | 11.7 s |
| Amazon Nova Pro | 0.43 | 0.00168 | 4.7 s |

Haiku agreed best with the human and had a stable p95, but cost about 3.5× Mistral per call. At
a few cents per interview, agreement won. Source: [`results/baseline_v1.md`](../results/baseline_v1.md).

### Judge prompt v1 → v2 (Claude Haiku 4.5, test split)

| Metric | v1 | v2 |
| --- | --- | --- |
| Weighted kappa | 0.61 | **0.82** |
| MAE | 1.00 | **0.62** |
| Within ±1 of the human | 76.2% | **100.0%** |
| Verbosity bias (judge − human on rambling answers, all splits) | +1.40 | **+0.30** |
| Verifiable quotes (all splits) | 65.7% | **77.1%** |
| Mean cost per call (USD) | 0.00356 | 0.00383 (**worse**, +8%) |

Error analysis on dev showed v1 was lenient: implicit criteria counted as met, a 5 needed no
proof, long answers scored higher, and quotes were paraphrased. v2 asks the judge to quote before
scoring, uses harder anchors for 4 and 5, and states that length earns nothing. The longer
reasoning costs a little more. Source: [`results/judge_v1_vs_v2.md`](../results/judge_v1_vs_v2.md).

### Tool decisions (set B, Claude Haiku 4.5)

The right action was chosen in **80.0%** of all 40 moments (75.0% on test). The confusion matrix
shows the misses are follow-ups asked where the expected move was the next question; "end" was
always right (12/12). The action counted is the effective one: the code caps follow-ups (2 per question, 1 on the web) whatever the model asks for.

### Robustness (set D)

| Scenario | Attacks that worked | Blocked by guardrail | Guardrail false positives |
| --- | --- | --- | --- |
| Claude Haiku 4.5 | **0.0%** (0/30) | n/a | n/a |
| Haiku + Bedrock Guardrails | **0.0%** (0/30) | 8 | 1 |

Delimiters, schema validation and literal quote checks were enough on this set. The guardrail
blocked 8 attacks that Haiku already resisted and added one false positive, so it stayed out of
production. Source:
[`results/robustez_v1.md`](../results/robustez_v1.md).

### Production (AWS demo, 2026-11-17)

| Metric | Value |
| --- | --- |
| Text model calls | 456, **0 errors** |
| Completed text interviews | 19 |
| Text cost per completed interview | **US$ 0.0587** (all calls of the day ÷ reports, so an upper bound) |
| Text call latency p50 / p95 | 1.3 s / 4.0 s |
| Voice: time to first audio, median / p90 | **1.31 s / 1.49 s** (11 sessions) |

Source: [`results/production_summary.md`](../results/production_summary.md), which holds
aggregates of the production run records. The records themselves contain visitor text and are
not published.

## Limitations

- **Small sets.** The test split has 21 judge items; one disagreement moves kappa visibly. Read
  the numbers as a direction, not a benchmark.
- **One human rater.** The labels come from the project owner alone, so there is no inter-rater
  agreement.
- **Synthetic answers.** Real candidates ramble and hesitate differently, especially in voice.
- **Set C has no score**, and set D has 30 items. A red-team with the Promptfoo plugins (task 6.2)
  was not run.
- **Bedrock-only comparison.** The planned comparison with Groq and Gemini (task 6.1) was not run
  before the account closed.

## Reproducing

The metric tables (`results/*.md`) are committed. The raw Promptfoo exports (`results/*.json`)
and new runs need model access (Bedrock), which this repo no longer has.

```bash
uv run python scripts/doc_numbers.py                     # every number cited in the docs
uv run pytest tests/test_eval_regression.py --no-cov     # set A replay, no model calls
npx promptfoo eval -c evals/promptfooconfig.yaml         # needs AWS credentials
```
