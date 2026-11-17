"""Static checks of the backend image (spec 3.9, R8). `docker run` itself is checked by hand."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _dockerfile() -> str:
    return (ROOT / "Dockerfile").read_text(encoding="utf-8")


def _ignored() -> set[str]:
    lines = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    return {line.strip().rstrip("/") for line in lines if line.strip() and not line.startswith("#")}


def test_image_is_arm64_python_312() -> None:
    text = _dockerfile()
    assert "--platform=linux/arm64" in text
    assert "python:3.12-slim" in text


def test_installs_only_production_dependencies_from_the_lock() -> None:
    text = _dockerfile()
    assert "uv sync --frozen --no-dev" in text
    assert "ghcr.io/astral-sh/uv:" in text and "uv:latest" not in text


def test_copies_runtime_folders() -> None:
    text = _dockerfile()
    for folder in ("src", "prompts", "config", "cases"):
        assert f"COPY {folder}" in text


def test_serves_the_agentcore_contract_on_8080() -> None:
    text = _dockerfile()
    assert "EXPOSE 8080" in text
    assert "--factory" in text and "mia.api.main:build_app" in text
    assert '"--port", "8080"' in text


def test_secrets_and_dev_files_stay_out_of_the_build_context() -> None:
    assert {".env", ".env.*", "runs", "frontend", "tests", ".venv", "node_modules"} <= _ignored()


def test_no_credentials_in_the_dockerfile() -> None:
    text = _dockerfile().upper()
    assert "AWS_ACCESS_KEY_ID" not in text and "AWS_SECRET_ACCESS_KEY" not in text
