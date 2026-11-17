"""Static checks on the GitHub Actions workflow (task 4.8)."""

from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "ci.yml"


def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def job_text(name: str) -> str:
    return yaml.safe_dump(workflow()["jobs"][name], allow_unicode=True)


def test_four_visible_jobs() -> None:
    assert set(workflow()["jobs"]) == {"lint", "tests", "eval-quick", "terraform"}


def test_lint_checks_style_and_format() -> None:
    text = job_text("lint")
    assert "ruff check ." in text and "ruff format --check ." in text


def test_tests_and_quick_eval() -> None:
    assert "pytest" in job_text("tests")
    quick = job_text("eval-quick")
    assert "tests/test_eval_regression.py" in quick
    assert (
        workflow()["jobs"]["eval-quick"]["name"] == "Eval rápido (conjunto A, respostas gravadas)"
    )


def test_terraform_without_aws() -> None:
    text = job_text("terraform")
    assert "terraform fmt -check -recursive" in text
    assert "-backend=false" in text and "terraform validate" in text
    assert "terraform plan" not in text


def test_no_secrets_or_cloud_credentials() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    for forbidden in ("secrets.", "aws-actions", "id-token: write"):
        assert forbidden not in raw
    assert workflow()["permissions"] == {"contents": "read"}
