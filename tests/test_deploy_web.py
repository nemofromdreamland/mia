"""Frontend deploy script (task 4.6), with a fake command runner."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import deploy_web  # noqa: E402

OUTPUTS = {
    "api_url": {"value": "https://abc.execute-api.us-east-1.amazonaws.com/"},
    "web_bucket": {"value": "mia-web-123"},
    "web_distribution_id": {"value": "E123"},
}


class FakeRunner:
    def __init__(self, *, fail_build: bool = False) -> None:
        self.calls: list[tuple[list[str], dict[str, str] | None]] = []
        self.fail_build = fail_build

    def __call__(self, cmd: list[str], env: dict[str, str] | None = None) -> str:
        self.calls.append((cmd, env))
        if cmd[0] == "terraform":
            return json.dumps(OUTPUTS)
        if cmd[0] == "npm" and self.fail_build:
            raise deploy_web.CommandError("npm run: tsc failed")
        return ""

    def tools(self) -> list[str]:
        return [cmd[0] for cmd, _ in self.calls]


def test_api_base_strips_trailing_slash() -> None:
    assert deploy_web.api_base("https://x/") == "https://x"
    assert deploy_web.api_base("https://x") == "https://x"


def test_outputs() -> None:
    assert deploy_web.outputs(FakeRunner()) == {
        "api_url": "https://abc.execute-api.us-east-1.amazonaws.com/",
        "web_bucket": "mia-web-123",
        "web_distribution_id": "E123",
    }


def test_deploy_commands() -> None:
    assets, rest, invalidate = deploy_web.deploy_commands("b", "E1")
    assert assets[:4] == ["aws", "s3", "sync", "frontend/dist/assets"]
    assert "s3://b/assets" in assets and "public, max-age=31536000, immutable" in assets
    assert rest[:4] == ["aws", "s3", "sync", "frontend/dist"]
    assert "--delete" in rest and "no-cache" in rest and "assets/*" in rest
    assert invalidate[:3] == ["aws", "cloudfront", "create-invalidation"]
    assert "E1" in invalidate and "/*" in invalidate
    for cmd in (assets, rest, invalidate):
        assert cmd[-4:] == ["--profile", "mia", "--region", "us-east-1"]


def test_full_run_order_and_build_env() -> None:
    run = FakeRunner()
    assert deploy_web.main([], run=run) == 0
    assert run.tools() == ["terraform", "npm", "aws", "aws", "aws"]
    build_cmd, env = run.calls[1]
    assert build_cmd == ["npm", "--prefix", "frontend", "run", "build"]
    assert env == {"VITE_API_BASE_URL": "https://abc.execute-api.us-east-1.amazonaws.com"}


def test_build_failure_stops_before_upload() -> None:
    run = FakeRunner(fail_build=True)
    assert deploy_web.main([], run=run) == 1
    assert "aws" not in run.tools()


def test_dry_run(capsys: pytest.CaptureFixture[str]) -> None:
    run = FakeRunner()
    assert deploy_web.main(["--dry-run"], run=run) == 0
    assert run.tools() == ["terraform"]
    out = capsys.readouterr().out
    assert "VITE_API_BASE_URL=https://abc.execute-api.us-east-1.amazonaws.com" in out
    assert "create-invalidation" in out
