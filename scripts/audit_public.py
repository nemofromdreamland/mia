"""Secrecy and personal-data audit for the public repository (task 6.4, step 1).

Scans tracked + untracked (not ignored) files, and optionally every line ever
added in git history, for keys, AWS identifiers, endpoints, local paths and
personal data. Output shows only path, line, kind and a MASKED value.

Usage:
    uv run python scripts/audit_public.py            # working tree
    uv run python scripts/audit_public.py --history  # + every commit

Personal identifiers (names, usernames) are never written in this repo: pass
them at run time with MIA_AUDIT_IDENTITIES="name1,name2" (comma-separated).
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml
from pydantic import BaseModel

DEFAULT_ALLOWLIST = Path(__file__).with_name("audit_allowlist.yaml")

PATTERNS: dict[str, re.Pattern[str]] = {
    "aws_key": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "groq_key": re.compile(r"\bgsk_[A-Za-z0-9]{20,}"),
    "secret_key": re.compile(r"\b[sp]k-(?:lf-|ant-|proj-)?[A-Za-z0-9-]{20,}"),
    "google_key": re.compile(r"\bAIza[0-9A-Za-z_-]{30,}"),
    "aws_account": re.compile(
        r"arn:aws:[a-z0-9-]+:[a-z0-9-]*:\d{12}|\b\d{12}\.dkr\.ecr|\bmia-[a-z]+-\d{12}\b"
    ),
    "api_gateway": re.compile(r"\b[a-z0-9]{10}\.execute-api\.[a-z0-9-]+\.amazonaws\.com"),
    "cloudfront": re.compile(r"\b[a-z0-9]{13,14}\.cloudfront\.net"),
    "local_path": re.compile(
        r"[A-Za-z]:\\{1,2}Users\\{1,2}[A-Za-z0-9_.-]+|/[cC]/Users/[A-Za-z0-9_.-]+"
    ),
    "email": re.compile(r"(?<![\w@])[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9.-]*[A-Za-z]{2,}"),
    "cpf": re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"),
    "phone": re.compile(r"\+55\s?\(?\d{2}\)?\s?9?\d{4}-?\d{4}|\(\d{2}\)\s?9?\d{4}-\d{4}"),
}

FORBIDDEN_FILES = re.compile(
    r"(^|/)(\.env(\.[^/]*)?|[^/]*\.tfstate(\.backup)?|[^/]*\.tfvars(\.json)?|[^/]*\.pem)$"
)
FORBIDDEN_OK = re.compile(r"\.example$")


class Finding(BaseModel):
    kind: str
    path: str
    line: int
    masked: str
    commit: str | None = None
    value: str = ""  # used only for allowlist matching; never printed

    def render(self) -> str:
        where = f"{self.commit[:8]}:" if self.commit else ""
        return f"{self.kind} | {where}{self.path}:{self.line} | {self.masked}"


def mask(value: str) -> str:
    if len(value) <= 8:
        return "***"
    return f"{value[:6]}***{value[-2:]}"


def _patterns() -> dict[str, re.Pattern[str]]:
    patterns = dict(PATTERNS)
    names = [n.strip() for n in os.environ.get("MIA_AUDIT_IDENTITIES", "").split(",") if n.strip()]
    if names:
        patterns["identity"] = re.compile("|".join(re.escape(n) for n in names), re.IGNORECASE)
    return patterns


def scan_text(path: str, text: str, commit: str | None = None) -> list[Finding]:
    findings: list[Finding] = []
    patterns = _patterns()
    for number, line in enumerate(text.splitlines(), start=1):
        findings.extend(_scan_line(path, number, line, commit, patterns))
    return findings


def _scan_line(
    path: str, number: int, line: str, commit: str | None, patterns: dict[str, re.Pattern[str]]
) -> list[Finding]:
    return [
        Finding(
            kind=kind,
            path=path,
            line=number,
            masked=mask(m.group(0)),
            commit=commit,
            value=m.group(0),
        )
        for kind, pattern in patterns.items()
        for m in pattern.finditer(line)
    ]


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout


def scan_tree(repo: Path) -> list[Finding]:
    files = _git(repo, "ls-files", "--cached", "--others", "--exclude-standard").splitlines()
    findings: list[Finding] = []
    for rel in files:
        full = repo / rel
        if not full.is_file():
            continue
        data = full.read_bytes()
        if b"\0" in data[:8000]:
            continue
        findings.extend(scan_text(rel, data.decode("utf-8", errors="replace")))
        findings.extend(_forbidden(rel, None))
    return findings


def _forbidden(path: str, commit: str | None) -> list[Finding]:
    if FORBIDDEN_FILES.search(path) and not FORBIDDEN_OK.search(path):
        return [
            Finding(
                kind="forbidden_file", path=path, line=0, masked=path, commit=commit, value=path
            )
        ]
    return []


_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)")


def scan_history(repo: Path) -> list[Finding]:
    """Scan every line ever added, in every commit of every ref."""
    log = _git(repo, "log", "--all", "-p", "--no-color", "--no-ext-diff", "--format=__commit__ %H")
    patterns = _patterns()
    findings: list[Finding] = []
    commit, path, number = None, "", 0
    for raw in log.splitlines():
        if raw.startswith("__commit__ "):
            commit = raw.split()[1]
        elif raw.startswith("+++ "):
            path = raw[6:] if raw.startswith("+++ b/") else raw[4:]
            findings.extend(_forbidden(path, commit))
        elif m := _HUNK.match(raw):
            number = int(m.group(1))
        elif raw.startswith("+"):
            findings.extend(_scan_line(path, number, raw[1:], commit, patterns))
            number += 1
        elif raw.startswith(" "):
            number += 1
    return findings


def _load_allowlist(allow: Path) -> list[dict[str, str]]:
    return yaml.safe_load(allow.read_text(encoding="utf-8")) or []


def _allowed(finding: Finding, rule: dict[str, str]) -> bool:
    return (
        fnmatch.fnmatch(finding.kind, rule["kind"])
        and fnmatch.fnmatch(finding.path, rule.get("path", "*"))
        and re.search(rule.get("value", ".*"), finding.value) is not None
    )


def apply_allowlist(findings: list[Finding], allow: Path) -> list[Finding]:
    rules = _load_allowlist(allow)
    return [f for f in findings if not any(_allowed(f, r) for r in rules)]


def _dedupe(findings: list[Finding]) -> list[Finding]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[Finding] = []
    for f in findings:
        key = (f.kind, f.path, f.value)
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return unique


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--allowlist", type=Path, default=DEFAULT_ALLOWLIST)
    parser.add_argument("--history", action="store_true", help="also scan every commit")
    args = parser.parse_args(argv)

    findings = scan_tree(args.repo)
    if args.history:
        findings += scan_history(args.repo)
    remaining = _dedupe(apply_allowlist(findings, args.allowlist))
    for f in remaining:
        print(f.render())
    scope = "working tree + history" if args.history else "working tree"
    print(f"{len(remaining)} findings outside allowlist ({scope})")
    return 1 if remaining else 0


if __name__ == "__main__":
    sys.exit(main())
