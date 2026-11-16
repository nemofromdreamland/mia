"""Checks on the real eval set files (task 2.4): B (tools), C (plans) and D (robustness)."""

import importlib.util
import re
from collections import Counter
from pathlib import Path
from types import ModuleType

import pytest
import yaml

from mia.schemas import PlanCaseItem, ToolMomentItem

ROOT = Path(__file__).parents[1]
DATASETS = ROOT / "evals" / "datasets"
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def _load_io() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "eval_sets_io", ROOT / "scripts" / "eval_sets_io.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


io = _load_io()


def _questions() -> dict[str, list[str]]:
    data = yaml.safe_load((DATASETS / "questions.yaml").read_text(encoding="utf-8"))
    return {q["id"]: q["look_for"] for q in data["questions"]}


def _assert_split_70_30(splits: list[str], stratum_size: int, label: str) -> None:
    dev = splits.count("dev")
    assert abs(dev - round(0.7 * stratum_size)) <= 1, f"{label}: {dev} dev of {stratum_size}"


def _assert_no_foreign_email(text: str) -> None:
    for email in EMAIL.findall(text):
        assert email.endswith("@example.com"), email


# ---------------------------------------------------------------- set B (tools)


@pytest.fixture(scope="module")
def tools() -> list[ToolMomentItem]:
    return io.load_jsonl(DATASETS / "tools.jsonl", ToolMomentItem)


def test_tools_size_and_actions(tools: list[ToolMomentItem]) -> None:
    assert 36 <= len(tools) <= 44
    counts = Counter(item.expected.action for item in tools)
    assert set(counts) == {"follow_up", "next_question", "end"}
    assert min(counts.values()) >= 8


def test_tools_ids_unique_and_questions_exist(tools: list[ToolMomentItem]) -> None:
    ids = [item.item_id for item in tools]
    assert len(ids) == len(set(ids))
    known = _questions()
    assert all(item.question_id in known for item in tools)


def test_tools_must_address_comes_from_look_for(tools: list[ToolMomentItem]) -> None:
    known = _questions()
    for item in tools:
        for wanted in item.expected.follow_up_must_address:
            assert wanted in known[item.question_id], item.item_id


def test_tools_time_is_consistent(tools: list[ToolMomentItem]) -> None:
    for item in tools:
        if item.minutes_left <= 0:
            assert item.expected.action == "end", item.item_id
        if item.expected.action == "end":
            assert item.minutes_left <= 0, item.item_id


def test_tools_have_edge_cases(tools: list[ToolMomentItem]) -> None:
    weak_no_room = [i for i in tools if i.follow_ups_left == 0 and i.minutes_left > 0]
    assert any(i.expected.action == "next_question" for i in weak_no_room)
    assert any(i.history for i in tools) and any(not i.history for i in tools)


def test_tools_split_70_30_by_action(tools: list[ToolMomentItem]) -> None:
    for action in ("follow_up", "next_question", "end"):
        group = [i for i in tools if i.expected.action == action]
        _assert_split_70_30([i.split for i in group], len(group), action)


def test_tools_no_real_personal_data(tools: list[ToolMomentItem]) -> None:
    for item in tools:
        _assert_no_foreign_email(item.answer + item.history + item.note)


# ---------------------------------------------------------------- set C (plans)


@pytest.fixture(scope="module")
def plans() -> list[PlanCaseItem]:
    return io.load_jsonl(DATASETS / "plans.jsonl", PlanCaseItem)


def test_plans_five_cases_and_one_extra(plans: list[PlanCaseItem]) -> None:
    assert len(plans) == 6
    assert Counter(item.source for item in plans) == {"case": 5, "extra": 1}
    case_ids = {p.name for p in (ROOT / "cases").iterdir() if p.is_dir()}
    from_cases = {Path(i.cv_path).parent.name for i in plans if i.source == "case"}
    assert from_cases == case_ids
    assert len({i.item_id for i in plans}) == 6


def test_plans_files_exist_and_match_case_yaml(plans: list[PlanCaseItem]) -> None:
    for item in plans:
        assert (ROOT / item.cv_path).is_file(), item.item_id
        assert (ROOT / item.job_path).is_file(), item.item_id
        if item.source == "case":
            meta = yaml.safe_load((ROOT / item.job_path).with_name("case.yaml").read_text("utf-8"))
            assert item.persona == meta["persona"] and item.language == meta["language"]
        else:
            assert item.cv_path.startswith("evals/datasets/plan_extra/")


def test_plans_gap_keywords_appear_in_job(plans: list[PlanCaseItem]) -> None:
    for item in plans:
        job = (ROOT / item.job_path).read_text(encoding="utf-8").lower()
        for keyword in item.expected.gap_keywords:
            assert keyword.lower() in job, f"{item.item_id}: {keyword}"


def test_plans_split_4_dev_2_test_with_extra_in_test(plans: list[PlanCaseItem]) -> None:
    assert Counter(i.split for i in plans) == {"dev": 4, "test": 2}
    assert next(i for i in plans if i.source == "extra").split == "test"


def test_plans_no_real_personal_data(plans: list[PlanCaseItem]) -> None:
    for item in plans:
        for path in (item.cv_path, item.job_path):
            _assert_no_foreign_email((ROOT / path).read_text(encoding="utf-8"))
