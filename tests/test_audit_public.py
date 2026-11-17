"""Tests for scripts/audit_public.py (task 6.4, step 1)."""

import subprocess
from pathlib import Path

import pytest

from scripts.audit_public import (
    Finding,
    apply_allowlist,
    main,
    mask,
    scan_history,
    scan_text,
)


def _kinds(findings: list[Finding]) -> list[str]:
    return [f.kind for f in findings]


def test_mask_keeps_six_first_and_two_last() -> None:
    assert mask("AKIAABCDEFGHIJKLMNOP") == "AKIAAB***OP"


def test_mask_short_value_is_fully_hidden() -> None:
    assert mask("abc") == "***"


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("key=AKIAABCDEFGHIJKLMNOP", "aws_key"),
        ("GROQ=gsk_" + "a" * 30, "groq_key"),
        ("x sk-lf-" + "b" * 24, "secret_key"),
        ("arn:aws:iam::123456789012:role/x", "aws_account"),
        ("https://abcdefghij.execute-api.us-east-1.amazonaws.com/prod", "api_gateway"),
        ("https://d1234567890abc.cloudfront.net", "cloudfront"),
        ("path C:\\Users\\fulano\\x", "local_path"),
        ("mail me at someone@gmail.com", "email"),
        ("cpf 987.654.321-00", "cpf"),
    ],
)
def test_scan_text_detects(text: str, kind: str) -> None:
    findings = scan_text("a.txt", text)
    assert kind in _kinds(findings)
    assert all("***" in f.masked for f in findings)


def test_scan_text_reports_line_number() -> None:
    findings = scan_text("a.txt", "ok\nok\nAKIAABCDEFGHIJKLMNOP\n")
    assert findings[0].line == 3
    assert findings[0].path == "a.txt"


def test_scan_text_ignores_decorators() -> None:
    assert scan_text("a.py", "@pytest.fixture\n@router.get\n") == []


def test_allowlist_removes_matching_finding(tmp_path: Path) -> None:
    allow = tmp_path / "allow.yaml"
    allow.write_text(
        "- kind: email\n  value: '@example\\.com$'\n  path: '*'\n  reason: fake domain\n",
        encoding="utf-8",
    )
    findings = scan_text("cv.md", "ana@example.com")
    assert apply_allowlist(findings, allow) == []


def test_allowlist_keeps_other_findings(tmp_path: Path) -> None:
    allow = tmp_path / "allow.yaml"
    allow.write_text(
        "- kind: email\n  value: '@example\\.com$'\n  path: '*'\n  reason: fake domain\n",
        encoding="utf-8",
    )
    findings = scan_text("cv.md", "ana@gmail.com")
    assert len(apply_allowlist(findings, allow)) == 1


def test_allowlist_respects_path_glob(tmp_path: Path) -> None:
    allow = tmp_path / "allow.yaml"
    allow.write_text(
        "- kind: cpf\n  value: '.*'\n  path: 'tests/*'\n  reason: fixture\n",
        encoding="utf-8",
    )
    kept = apply_allowlist(scan_text("src/x.py", "987.654.321-00"), allow)
    assert len(kept) == 1


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _repo(tmp_path: Path, content: str) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    (repo / "f.txt").write_text(content, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "c1")
    return repo


def test_scan_history_finds_secret_removed_later(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "AKIAABCDEFGHIJKLMNOP\n")
    (repo / "f.txt").write_text("clean\n", encoding="utf-8")
    _git(repo, "commit", "-qam", "c2")
    findings = scan_history(repo)
    assert "aws_key" in _kinds(findings)
    assert findings[0].commit is not None


def test_main_clean_repo_exits_zero(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "nothing here\n")
    allow = tmp_path / "allow.yaml"
    allow.write_text("[]\n", encoding="utf-8")
    assert main(["--repo", str(repo), "--allowlist", str(allow), "--history"]) == 0


def test_main_dirty_repo_exits_one(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = _repo(tmp_path, "AKIAABCDEFGHIJKLMNOP\n")
    allow = tmp_path / "allow.yaml"
    allow.write_text("[]\n", encoding="utf-8")
    assert main(["--repo", str(repo), "--allowlist", str(allow)]) == 1
    out = capsys.readouterr().out
    assert "AKIAABCDEFGHIJKLMNOP" not in out
    assert "AKIAAB***OP" in out


def test_tracked_forbidden_files_are_findings(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "x\n")
    (repo / "terraform.tfstate").write_text("{}", encoding="utf-8")
    _git(repo, "add", "-f", ".")
    _git(repo, "commit", "-qm", "c2")
    allow = tmp_path / "allow.yaml"
    allow.write_text("[]\n", encoding="utf-8")
    assert main(["--repo", str(repo), "--allowlist", str(allow), "--history"]) == 1


def test_allowlist_kind_wildcard(tmp_path: Path) -> None:
    allow = tmp_path / "allow.yaml"
    allow.write_text(
        "- kind: '*'\n  value: '.*'\n  path: 'tests/*'\n  reason: samples\n", encoding="utf-8"
    )
    assert apply_allowlist(scan_text("tests/a.py", "AKIAABCDEFGHIJKLMNOP"), allow) == []
