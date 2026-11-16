"""Command line: `mia simulate` runs prep → text interview → report in the terminal.

The dialog goes to stderr; stdout carries only the final JSON, so
`mia simulate ... > relatorio.json` works.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from pydantic import ValidationError

from mia.interviewer import InterviewError
from mia.llm import ModelConfigError
from mia.prep_graph import PrepInput
from mia.simulation import (
    SimulationDeps,
    SimulationError,
    begin,
    default_deps,
    finish,
    prepare,
    reply,
    stop,
)

STOP_COMMAND = "/fim"
MIN_MINUTES, MAX_MINUTES = 5, 45


def _minutes(value: str) -> int:
    try:
        minutes = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid number: {value!r}") from exc
    if not MIN_MINUTES <= minutes <= MAX_MINUTES:
        raise argparse.ArgumentTypeError(f"must be between {MIN_MINUTES} and {MAX_MINUTES}")
    return minutes


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mia", description="MIA — Mock Interview Assistant")
    commands = parser.add_subparsers(dest="command", required=True)
    sim = commands.add_parser("simulate", help="simulate an interview from a CV and a job")
    sim.add_argument("--cv", type=Path, required=True, help="CV file (.pdf, .md or .txt)")
    sim.add_argument("--job", type=Path, required=True, help="job description text file")
    sim.add_argument("--persona", choices=["hr", "technical", "manager"], required=True)
    sim.add_argument("--level", choices=["internship", "junior", "mid"], default="junior")
    sim.add_argument("--minutes", type=_minutes, default=20, help="5 to 45 (default 20)")
    sim.add_argument("--language", choices=["pt-BR", "en-US"], default="pt-BR")
    return parser


def _read_job(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SimulationError(f"{path}: não foi possível ler a vaga ({exc.strerror})") from exc


def _say(stream: TextIO, text: str) -> None:
    print(text, file=stream, flush=True)


def _interview(deps: SimulationDeps, state, first_text: str, stdin: TextIO, stderr: TextIO):
    """Ask/answer loop; ends on the plan, on `/fim` or on EOF."""
    _say(stderr, f"\nEntrevistador: {first_text}")
    while not state.ended:
        stderr.write("\nVocê> ")
        stderr.flush()
        line = stdin.readline()
        if line == "" or line.strip() == STOP_COMMAND:
            state, turn = stop(deps, state)
            _say(stderr, f"\nEntrevistador: {turn.interviewer_text}")
            break
        try:
            step = reply(deps, state, line)
        except InterviewError as exc:
            _say(stderr, f"({exc}) Tente de novo.")
            continue
        state = step.state
        _say(stderr, f"\nEntrevistador: {step.next_turn.interviewer_text}")
    return state


def run_simulate(
    args: argparse.Namespace,
    deps: SimulationDeps,
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    try:
        data = PrepInput(
            cv_path=args.cv,
            job_text=_read_job(args.job),
            persona=args.persona,
            level=args.level,
            estimated_minutes=args.minutes,
            language=args.language,
        )
        _say(stderr, "Preparando a entrevista...")
        session, prepared = prepare(deps, data)
        state, first = begin(deps, session, prepared.plan)
        state = _interview(deps, state, first.interviewer_text, stdin, stderr)
        _say(stderr, "\nGerando o relatório...")
        result = finish(deps, state)
    except SimulationError as exc:
        _say(stderr, str(exc))
        return 1
    output = {
        "session_id": state.session_id,
        "report": result.report.model_dump(mode="json"),
        "summary": result.summary.model_dump(mode="json"),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2), file=stdout)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    for stream in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    try:
        _read_job(args.job)  # fail fast, before any model is configured
        return run_simulate(args, default_deps(args.persona))
    except SimulationError as exc:
        _say(sys.stderr, str(exc))
        return 1
    except (ModelConfigError, ValidationError) as exc:
        _say(sys.stderr, f"Configuração dos modelos inválida: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
