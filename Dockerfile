# Backend image for the AgentCore Runtime (ARM64, /ping + /invocations on port 8080).
# Build: docker build --platform linux/arm64 -t mia-backend .
# Local: docker run --rm -p 8080:8080 -e MIA_STORAGE=memory mia-backend
FROM --platform=linux/arm64 python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.8.22 /uv /bin/uv

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Dependencies first (cached layer), without the project and without the dev group.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Code and the data it reads at runtime (paths are resolved from the repo root).
COPY src ./src
COPY prompts ./prompts
COPY config ./config
COPY cases ./cases
RUN uv sync --frozen --no-dev && mkdir -p runs \
    && useradd --create-home --uid 1000 mia && chown -R mia /app/runs
USER mia

EXPOSE 8080
CMD ["uvicorn", "--factory", "mia.api.main:build_app", "--host", "0.0.0.0", "--port", "8080"]
