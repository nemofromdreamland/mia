"""Task 4.6: build the frontend against the deployed API and publish it to S3 + CloudFront.

Usage:
    uv run python scripts/deploy_web.py [--dry-run]

Reads `api_url`, `web_bucket` and `web_distribution_id` from `terraform -chdir=infra output`.
Exit codes: 0 published (or dry run), 1 a command failed.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = "frontend/dist"
AWS_SUFFIX = ["--profile", "mia", "--region", "us-east-1"]
IMMUTABLE = "public, max-age=31536000, immutable"

Runner = Callable[[list[str], dict[str, str] | None], str]


class CommandError(Exception):
    """A command exited with a non-zero code."""


def run_command(cmd: list[str], env: dict[str, str] | None = None) -> str:
    """Run `cmd` in the repo root (extra env merged in); raise CommandError on failure."""
    exe = shutil.which(cmd[0]) or cmd[0]  # npm is npm.cmd on Windows
    result = subprocess.run(
        [exe, *cmd[1:]],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env={**os.environ, **(env or {})},
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()[-500:]
        raise CommandError(f"{cmd[0]} {cmd[1]}: {detail}")
    return result.stdout


def outputs(run: Runner) -> dict[str, str]:
    raw = json.loads(run(["terraform", "-chdir=infra", "output", "-json"], None))
    keys = ("api_url", "web_bucket", "web_distribution_id")
    return {key: str(raw[key]["value"]) for key in keys}


def api_base(url: str) -> str:
    """`api.ts` appends `/cases` etc., so the base must not end with a slash."""
    return url.rstrip("/")


def build_command() -> list[str]:
    return ["npm", "--prefix", "frontend", "run", "build"]


def deploy_commands(bucket: str, distribution: str) -> list[list[str]]:
    """Hashed assets cached for a year; index.html and the rest always revalidated."""
    return [
        ["aws", "s3", "sync", f"{DIST}/assets", f"s3://{bucket}/assets", "--delete",
         "--cache-control", IMMUTABLE, *AWS_SUFFIX],
        ["aws", "s3", "sync", DIST, f"s3://{bucket}", "--delete", "--exclude", "assets/*",
         "--cache-control", "no-cache", *AWS_SUFFIX],
        ["aws", "cloudfront", "create-invalidation", "--distribution-id", distribution,
         "--paths", "/*", *AWS_SUFFIX],
    ]  # fmt: skip


def main(argv: Sequence[str] | None = None, run: Runner = run_command) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="só mostra os comandos")
    args = parser.parse_args(argv)
    try:
        out = outputs(run)
        env = {"VITE_API_BASE_URL": api_base(out["api_url"])}
        steps = deploy_commands(out["web_bucket"], out["web_distribution_id"])
        if args.dry_run:
            print(f"VITE_API_BASE_URL={env['VITE_API_BASE_URL']} " + " ".join(build_command()))
            for cmd in steps:
                print(" ".join(cmd))
            return 0
        print("$ " + " ".join(build_command()), flush=True)
        run(build_command(), env)
        for cmd in steps:
            print("$ " + " ".join(cmd), flush=True)
            run(cmd, None)
    except CommandError as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1
    print(f"OK: publicado em {out['web_bucket']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
