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

from mia.cases import CASES_DIR, CaseError, LoadedCase, load_case
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
    start_from_case,
    stop,
)

STOP_COMMAND = "/fim"
DEFAULT_LEVEL, DEFAULT_MINUTES, DEFAULT_LANGUAGE = "junior", 20, "pt-BR"
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
    sim = commands.add_parser(
        "simulate", help="simulate an interview (ready-made case or CV + job)"
    )
    mode = sim.add_mutually_exclusive_group(required=True)
    mode.add_argument("--case", help="id of a ready-made case in cases/")
    mode.add_argument("--cv", type=Path, help="CV file (.pdf, .md or .txt)")
    sim.add_argument("--job", type=Path, help="job description text file (with --cv)")
    sim.add_argument("--persona", choices=["hr", "technical", "manager"])
    sim.add_argument("--level", choices=["internship", "junior", "mid"])
    sim.add_argument("--minutes", type=_minutes, help="5 to 45 (default 20)")
    sim.add_argument("--language", choices=["pt-BR", "en-US"])
    return parser


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse and check the two modes (case × standalone); a bad mix exits with code 2."""
    parser = build_parser()
    args = parser.parse_args(argv)
    given = {"--persona": args.persona, "--level": args.level, "--language": args.language}
    if args.case:
        extras = [
            flag
            for flag, value in {**given, "--job": args.job, "--minutes": args.minutes}.items()
            if value is not None
        ]
        if extras:
            parser.error(f"--case already defines the interview; remove {', '.join(extras)}")
    elif args.job is None or args.persona is None:
        parser.error("--cv requires --job and --persona")
    return args


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


def _prepare_standalone(args: argparse.Namespace, deps: SimulationDeps, stderr: TextIO):
    data = PrepInput(
        cv_path=args.cv,
        job_text=_read_job(args.job),
        persona=args.persona,
        level=args.level or DEFAULT_LEVEL,
        estimated_minutes=args.minutes or DEFAULT_MINUTES,
        language=args.language or DEFAULT_LANGUAGE,
    )
    _say(stderr, "Preparando a entrevista...")
    session, prepared = prepare(deps, data)
    return session, prepared.plan


def run_simulate(
    args: argparse.Namespace,
    deps: SimulationDeps,
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
    loaded: LoadedCase | None = None,
) -> int:
    try:
        if loaded is not None:
            session, plan = start_from_case(deps, loaded), loaded.plan
        else:
            session, plan = _prepare_standalone(args, deps, stderr)
        state, first = begin(deps, session, plan)
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


def main(argv: Sequence[str] | None = None, cases_dir: Path = CASES_DIR) -> int:
    args = parse_args(argv)
    for stream in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    try:
        loaded = load_case(args.case, cases_dir) if args.case else None
        if loaded is None:
            _read_job(args.job)  # fail fast, before any model is configured
        persona = loaded.case.persona if loaded else args.persona
        return run_simulate(args, default_deps(persona), loaded=loaded)
    except (SimulationError, CaseError) as exc:
        _say(sys.stderr, str(exc))
        return 1
    except (ModelConfigError, ValidationError) as exc:
        _say(sys.stderr, f"Configuração dos modelos inválida: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
