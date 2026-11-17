# Running locally

The AWS demo is offline (the account closed on 2026-11-17), but the whole product runs on your
machine: the CLI, the API with in-memory storage, and the React frontend. You do **not** need
Terraform, DynamoDB or AgentCore. You do need access to a model for anything that talks or
scores.

## Requirements

- Python 3.12 and [uv](https://docs.astral.sh/uv/)
- Node.js and npm (frontend only)
- Model access. The default route for every prompt is **Claude Haiku 4.5 on Amazon Bedrock**
  (`config/models.yaml`), so you need an AWS profile with Bedrock model access in `us-east-1`.
  Voice also needs Amazon Nova 2 Sonic.

```bash
git clone <this repo> && cd mia
uv sync
cp .env.example .env      # set AWS_PROFILE and AWS_REGION (and GROQ_API_KEY if you use Groq)
```

## 1. Tests (no model, no keys)

```bash
uv run pytest             # 1,400+ tests, fakes only, coverage gate 80%
uv run ruff check .
cd frontend && npm ci && npm test
```

## 2. CLI interview

```bash
uv run mia simulate --case prompt-engineer-jr             # one of the 5 ready-made cases
uv run mia simulate --cv my_cv.md --job job.md --persona technical --level junior --minutes 10
```

`--cv` accepts `.pdf`, `.md` or `.txt`. **Use fictitious documents only**: `pii.py` masks
personal data before any model call, but this project never processes real CVs. There are
samples in `tests/fixtures/prep/`. Each model call is appended to `runs/<date>_adhoc.jsonl`.

## 3. Web app

Two terminals:

```bash
# terminal 1: API with in-memory repositories and quotas (state is lost on restart)
uv run uvicorn mia.api.dev:app --port 8000

# terminal 2: frontend; Vite proxies /api to port 8000
cd frontend && npm run dev
```

Open the URL Vite prints. Listing cases and creating a session work without any model call,
because screening and plans are pre-generated in `cases/`. Answers, scores and the report call
the model. The recruiter screen fills up as you finish interviews.

Voice uses the same server (`/ws`) and needs Nova 2 Sonic on Bedrock, a microphone and
headphones.

## Without AWS

All model access goes through `src/mia/llm.py` and `config/models.yaml`, so another provider is
a config change: point the routes in `prompt_models` at a model in the catalog (for example
`groq:openai/gpt-oss-120b`, which has a free tier). Two caveats:

- Only Claude Haiku 4.5 was evaluated for the production prompts; other models are untested
  here ([evaluation.md](evaluation.md)).
- `tests/test_prompt_models_guard.py` will flag the change, because each prompt version declares
  its route. That is intended: a real switch means new prompt versions.

Voice has no alternative: it needs Nova 2 Sonic.

## Useful files

| Path | What it is |
| --- | --- |
| `cases/<id>/` | Fictitious CV, job, screening and plan for each web case |
| `prompts/<name>/v<N>.yaml` | Versioned prompts with changelogs |
| `config/models.yaml` | Model catalog, prices, prompt routes |
| `runs/*.jsonl` | One record per model call |
| `scripts/doc_numbers.py` | Prints every number cited in the docs |
