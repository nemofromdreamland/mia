"""Task 4.4: build the ARM64 backend image and push it to ECR, tagged with the commit.

Usage:
    uv run python scripts/push_image.py [--dry-run] [--repo <ecr-url>]

The repository URL comes from `terraform -chdir=infra output -raw ecr_repository_url`.
Refuses to run with uncommitted changes in tracked files (the tag must match the code).
Exit codes: 0 pushed (or already there / dry run), 1 refused or command failed.
"""

import argparse
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILE = "mia"
REGION = "us-east-1"

Runner = Callable[[list[str], str | None], str]


class CommandError(Exception):
    """A command exited with a non-zero code."""


class DirtyTreeError(Exception):
    """Tracked files have uncommitted changes."""


def run_command(cmd: list[str], stdin: str | None = None) -> str:
    """Run `cmd` in the repo root and return stdout; raise CommandError on failure."""
    result = subprocess.run(cmd, input=stdin, capture_output=True, text=True, cwd=ROOT)
    if result.returncode != 0:
        raise CommandError(f"{cmd[0]} {cmd[1]}: {result.stderr.strip()[:300]}")
    return result.stdout


def commit_tag(run: Runner) -> str:
    """12-character hash of HEAD; refuses when tracked files changed."""
    if run(["git", "status", "--porcelain", "--untracked-files=no"], None).strip():
        raise DirtyTreeError("Há mudanças não commitadas: faça commit antes do push.")
    return run(["git", "rev-parse", "--short=12", "HEAD"], None).strip()


def repo_url(run: Runner, override: str | None) -> str:
    if override:
        return override
    return run(["terraform", "-chdir=infra", "output", "-raw", "ecr_repository_url"], None).strip()


def _aws(*args: str) -> list[str]:
    return ["aws", *args, "--profile", PROFILE, "--region", REGION]


def image_exists(run: Runner, repo: str, tag: str) -> bool:
    name = repo.split("/", 1)[1]
    try:
        run(
            _aws(
                "ecr",
                "describe-images",
                "--repository-name",
                name,
                "--image-ids",
                f"imageTag={tag}",
            ),
            None,
        )
    except CommandError:
        return False
    return True


def login(run: Runner, repo: str) -> None:
    """docker login with the ECR password on stdin (never on the command line)."""
    password = run(_aws("ecr", "get-login-password"), None).strip()
    registry = repo.split("/", 1)[0]
    run(["docker", "login", "--username", "AWS", "--password-stdin", registry], password)


def push_commands(repo: str, tag: str) -> list[list[str]]:
    image = f"{repo}:{tag}"
    return [
        ["docker", "build", "--platform", "linux/arm64", "-t", image, "."],
        ["docker", "push", image],
    ]


def main(argv: Sequence[str] | None = None, run: Runner = run_command) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="só mostra os comandos")
    parser.add_argument("--repo", help="URL do repositório ECR (padrão: output do Terraform)")
    args = parser.parse_args(argv)
    try:
        tag = commit_tag(run)
        repo = repo_url(run, args.repo)
        if args.dry_run:
            print(
                "aws ecr get-login-password | docker login --password-stdin " + repo.split("/")[0]
            )
            for cmd in push_commands(repo, tag):
                print(" ".join(cmd))
            return 0
        if image_exists(run, repo, tag):
            print(f"Já existe: {repo}:{tag} (tags imutáveis). Nada a fazer.")
            return 0
        login(run, repo)
        for cmd in push_commands(repo, tag):
            print("$ " + " ".join(cmd), flush=True)
            run(cmd, None)
    except (DirtyTreeError, CommandError) as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1
    print(f"OK: {repo}:{tag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
