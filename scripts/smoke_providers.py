"""Smoke test (task 0.6): the same prompt on every catalog model, through llm.invoke.

Each call is recorded by llm.invoke as a RunRecord in runs/<date>_smoke-providers.jsonl.

Usage:
    uv run --env-file .env python scripts/smoke_providers.py
    uv run --env-file .env python scripts/smoke_providers.py --model groq:openai/gpt-oss-120b
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mia.llm import DEFAULT_RUNS_DIR, ModelsConfig, invoke, load_models_config
from mia.schemas import RunRecord

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

SMOKE_PROMPT_NAME = "smoke"
SMOKE_PROMPT_VERSION = 1
SMOKE_EXPERIMENT = "smoke-providers"
# Fixed, fictional prompt: no user data, so nothing to mask (pii.py is task 1.4).
SMOKE_SYSTEM = "Você é um assistente objetivo. Responda em português, em uma única frase."
SMOKE_USER = "O que um recrutador costuma avaliar numa entrevista comportamental?"
SMOKE_PARAMS: dict[str, Any] = {"temperature": 0}
PREVIEW_CHARS = 60


@dataclass(frozen=True)
class SmokeResult:
    ref: str
    ok: bool
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost_usd: float
    preview: str  # start of the answer or of the error, on one line


def make_preview(text: str) -> str:
    """Collapse whitespace (including newlines) and cut to PREVIEW_CHARS."""
    return " ".join(text.split())[:PREVIEW_CHARS]


def runs_file(runs_dir: Path) -> Path:
    """Today's (UTC) file for this experiment, the same name llm.append_run_record uses."""
    return runs_dir / f"{datetime.now(UTC).date().isoformat()}_{SMOKE_EXPERIMENT}.jsonl"


def _count_lines(path: Path) -> int:
    return len(path.read_text("utf-8").splitlines()) if path.exists() else 0


def _last_record(path: Path) -> RunRecord:
    return RunRecord.model_validate_json(path.read_text("utf-8").splitlines()[-1])


def _result_from_record(ref: str, record: RunRecord) -> SmokeResult:
    return SmokeResult(
        ref=ref,
        ok=record.error is None,
        input_tokens=record.input_tokens,
        output_tokens=record.output_tokens,
        latency_ms=record.latency_ms,
        cost_usd=record.cost_usd,
        preview=make_preview(record.error or record.output_raw),
    )


def run_smoke(
    refs: list[str],
    *,
    config: ModelsConfig,
    runs_dir: Path = DEFAULT_RUNS_DIR,
    chat_models: dict[str, BaseChatModel] | None = None,
) -> tuple[list[SmokeResult], Path]:
    """Call each model once, in order; a failure never stops the next models."""
    path = runs_file(runs_dir)
    results: list[SmokeResult] = []
    for ref in refs:
        lines_before = _count_lines(path)
        try:
            invoke(
                prompt_name=SMOKE_PROMPT_NAME,
                prompt_version=SMOKE_PROMPT_VERSION,
                system=SMOKE_SYSTEM,
                user=SMOKE_USER,
                input={},
                model=ref,
                params=dict(SMOKE_PARAMS),
                experiment=SMOKE_EXPERIMENT,
                config=config,
                runs_dir=runs_dir,
                chat_model=(chat_models or {}).get(ref),
            )
        except Exception as exc:
            if _count_lines(path) == lines_before:
                # Failed before calling the provider (e.g. missing package): no RunRecord.
                preview = make_preview(f"{type(exc).__name__}: {exc}")
                results.append(SmokeResult(ref, False, 0, 0, 0, 0.0, preview))
                continue
        results.append(_result_from_record(ref, _last_record(path)))
    return results, path


def format_table(results: list[SmokeResult]) -> str:
    header = ("modelo", "status", "entrada", "saída", "ms", "USD", "prévia")
    rows = [header] + [
        (
            r.ref,
            "ok" if r.ok else "erro",
            str(r.input_tokens),
            str(r.output_tokens),
            str(r.latency_ms),
            f"{r.cost_usd:.6f}",
            r.preview,
        )
        for r in results
    ]
    widths = [max(len(row[i]) for row in rows) for i in range(len(header) - 1)]
    return "\n".join(
        "  ".join(cell.ljust(width) for cell, width in zip(row, widths, strict=False))
        + "  "
        + row[-1]
        for row in rows
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Manda o mesmo prompt para os modelos do config/models.yaml e grava em runs/."
    )
    parser.add_argument(
        "--model",
        action="append",
        dest="models",
        metavar="REF",
        help="referência provedor:modelo do catálogo (pode repetir); padrão: todos",
    )
    args = parser.parse_args(argv)

    config = load_models_config()
    refs: list[str] = args.models or list(config.models)
    unknown = [ref for ref in refs if ref not in config.models]
    if unknown:
        print(f"Modelo fora do config/models.yaml: {', '.join(unknown)}", file=sys.stderr)
        return 2

    results, path = run_smoke(refs, config=config)
    print(format_table(results))
    print(f"\nRegistros em: {path}")
    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    # Windows pipes default to cp1252: print accents and model answers as UTF-8.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    sys.exit(main())
