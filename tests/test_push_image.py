"""Build/push script for the backend image (task 4.4), with a fake command runner."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import push_image  # noqa: E402

REPO = "123456789012.dkr.ecr.us-east-1.amazonaws.com/mia-backend"
TAG = "abc123def456"


class FakeRunner:
    """Records (command, stdin); answers known commands."""

    def __init__(self, *, dirty: str = "", exists: bool = False) -> None:
        self.calls: list[tuple[list[str], str | None]] = []
        self.dirty = dirty
        self.exists = exists

    def __call__(self, cmd: list[str], stdin: str | None = None) -> str:
        self.calls.append((cmd, stdin))
        joined = " ".join(cmd)
        if joined.startswith("git rev-parse"):
            return TAG + "\n"
        if joined.startswith("git status"):
            return self.dirty
        if joined.startswith("terraform"):
            return REPO
        if "describe-images" in joined:
            if not self.exists:
                raise push_image.CommandError("ImageNotFoundException")
            return "{}"
        if "get-login-password" in joined:
            return "SECRET-PASSWORD"
        return ""

    def tools(self) -> list[str]:
        return [cmd[0] for cmd, _ in self.calls]


def test_commit_tag() -> None:
    assert push_image.commit_tag(FakeRunner()) == TAG


def test_dirty_tree_refuses_without_docker() -> None:
    run = FakeRunner(dirty=" M src/mia/llm.py\n")
    assert push_image.main([], run=run) == 1
    assert "docker" not in run.tools()


def test_repo_from_terraform_or_override() -> None:
    run = FakeRunner()
    assert push_image.repo_url(run, None) == REPO
    assert run.calls[-1][0][:3] == ["terraform", "-chdir=infra", "output"]
    assert push_image.repo_url(run, "x/y") == "x/y"


def test_push_commands() -> None:
    build, push = push_image.push_commands(REPO, TAG)
    assert build == ["docker", "build", "--platform", "linux/arm64", "-t", f"{REPO}:{TAG}", "."]
    assert push == ["docker", "push", f"{REPO}:{TAG}"]


def test_full_run_order_and_password_on_stdin() -> None:
    run = FakeRunner()
    assert push_image.main([], run=run) == 0
    docker = [(cmd, stdin) for cmd, stdin in run.calls if cmd[0] == "docker"]
    assert [cmd[1] for cmd, _ in docker] == ["login", "build", "push"]
    login, stdin = docker[0]
    assert stdin == "SECRET-PASSWORD"
    assert "SECRET-PASSWORD" not in " ".join(login)
    assert login[-1] == REPO.split("/")[0]
    assert "--password-stdin" in login


def test_dry_run_calls_no_aws_or_docker(capsys: pytest.CaptureFixture[str]) -> None:
    run = FakeRunner()
    assert push_image.main(["--dry-run", "--repo", REPO], run=run) == 0
    assert set(run.tools()) <= {"git"}
    assert f"docker push {REPO}:{TAG}" in capsys.readouterr().out


def test_existing_tag_skips_build() -> None:
    run = FakeRunner(exists=True)
    assert push_image.main([], run=run) == 0
    assert "docker" not in run.tools()
