"""Checks the committed golden set A file (task 2.2, step 3)."""

import json
from collections import Counter
from pathlib import Path

import pytest

from mia.pii import mask_text
from mia.schemas import GoldenItem

DATASET = Path(__file__).parents[1] / "evals" / "datasets" / "judge_golden.jsonl"
EXPECTED_VARIANTS = {
    "level_5",
    "level_4",
    "level_3",
    "level_2",
    "level_1",
    "rambling",
    "paraphrase",
}


@pytest.fixture(scope="module")
def items() -> list[GoldenItem]:
    lines = DATASET.read_text(encoding="utf-8").splitlines()
    return [GoldenItem.model_validate(json.loads(line)) for line in lines if line.strip()]


def test_has_70_valid_items(items: list[GoldenItem]) -> None:
    assert len(items) == 70


def test_item_ids_are_unique(items: list[GoldenItem]) -> None:
    assert len({i.item_id for i in items}) == 70


def test_each_question_has_the_7_variants(items: list[GoldenItem]) -> None:
    by_question: dict[str, set[str]] = {}
    for item in items:
        by_question.setdefault(item.question.id, set()).add(item.variant)
    assert len(by_question) == 10
    assert all(variants == EXPECTED_VARIANTS for variants in by_question.values())


def test_paraphrase_points_to_level_3(items: list[GoldenItem]) -> None:
    for item in items:
        if item.variant == "paraphrase":
            assert item.paraphrase_of == f"{item.question.id}-level_3"
        else:
            assert item.paraphrase_of is None


def test_generated_by_groq(items: list[GoldenItem]) -> None:
    assert Counter(i.generated_by.split("|")[0] for i in items) == {"groq:openai/gpt-oss-120b": 70}


def test_no_personal_data(items: list[GoldenItem]) -> None:
    assert all(mask_text(i.answer_text) == i.answer_text for i in items)


def test_every_item_has_human_score_1_to_5(items: list[GoldenItem]) -> None:
    assert all(i.human_score is not None and 1 <= i.human_score <= 5 for i in items)


def test_every_item_has_a_split(items: list[GoldenItem]) -> None:
    assert all(i.split in {"dev", "test"} for i in items)


def test_split_is_49_dev_and_21_test(items: list[GoldenItem]) -> None:
    assert Counter(i.split for i in items) == {"dev": 49, "test": 21}


def test_split_is_7_dev_3_test_per_variant(items: list[GoldenItem]) -> None:
    counts = Counter((i.variant, i.split) for i in items)
    for variant in EXPECTED_VARIANTS:
        assert counts[(variant, "dev")] == 7
        assert counts[(variant, "test")] == 3


def test_paraphrase_shares_split_with_original(items: list[GoldenItem]) -> None:
    split_by_id = {i.item_id: i.split for i in items}
    for item in items:
        if item.paraphrase_of is not None:
            assert item.split == split_by_id[item.paraphrase_of]
