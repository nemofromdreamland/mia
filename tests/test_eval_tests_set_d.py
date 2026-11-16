"""Tests for evals/tests_set_d.py and evals/robustness_v1.yaml (task 2.8b, step 2)."""

import importlib.util
from pathlib import Path
from types import ModuleType

import yaml

from mia.schemas import RobustnessItem

EVALS = Path(__file__).parents[1] / "evals"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("tests_set_d", EVALS / "tests_set_d.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tests_set_d = _load()


def test_generates_one_test_per_item() -> None:
    tests = tests_set_d.generate_tests()
    assert len(tests) == 30
    assert len({t["vars"]["item_id"] for t in tests}) == 30


def test_item_var_is_a_valid_item() -> None:
    test = tests_set_d.generate_tests()[0]
    item = RobustnessItem.model_validate(test["vars"]["item"])
    assert item.item_id == test["description"] == test["vars"]["item_id"]


def test_first_five_tests_cover_every_attack_type() -> None:
    """--filter-first-n 5 must be a smoke run with one item per attack type."""
    tests = tests_set_d.generate_tests()[:5]
    types = {t["vars"]["item"]["attack_type"] for t in tests}
    assert len(types) == 5


def test_split_filter() -> None:
    tests = tests_set_d.generate_tests({"split": "test"})
    assert tests
    assert {t["vars"]["item"]["split"] for t in tests} == {"test"}


def test_config_has_two_scenarios_with_the_same_experiment() -> None:
    config = yaml.safe_load((EVALS / "robustness_v1.yaml").read_text(encoding="utf-8"))
    providers = {p["label"]: p["config"] for p in config["providers"]}
    assert set(providers) == {"haiku", "haiku+guardrail"}
    assert "guardrail" not in providers["haiku"]
    assert providers["haiku+guardrail"]["guardrail"] == "robustness"
    assert {c["experiment"] for c in providers.values()} == {"robustness_v1"}
