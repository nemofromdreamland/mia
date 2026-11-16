"""Structural checks for the golden set questions (task 2.1). No model calls."""

from collections import Counter
from pathlib import Path
from typing import Final

import pytest
import yaml

from mia.pii import mask_text
from mia.schemas import Question

QUESTIONS_PATH: Final[Path] = (
    Path(__file__).resolve().parent.parent / "evals" / "datasets" / "questions.yaml"
)


def _load_questions() -> list[Question]:
    data = yaml.safe_load(QUESTIONS_PATH.read_text(encoding="utf-8"))
    return [Question.model_validate(item) for item in data["questions"]]


@pytest.fixture(scope="module")
def questions() -> list[Question]:
    return _load_questions()


def test_has_ten_valid_questions(questions: list[Question]) -> None:
    assert len(questions) == 10


def test_phase_distribution(questions: list[Question]) -> None:
    assert Counter(q.phase for q in questions) == {"technical": 6, "behavioral": 4}


def test_ids_are_unique(questions: list[Question]) -> None:
    assert len({q.id for q in questions}) == len(questions)


def test_look_for_criteria_are_non_empty_and_distinct(questions: list[Question]) -> None:
    for q in questions:
        criteria = [c.strip() for c in q.look_for]
        assert 3 <= len(criteria) <= 4, q.id
        assert all(criteria), q.id
        assert len(set(criteria)) == len(criteria), q.id


def test_targets_concern_is_null(questions: list[Question]) -> None:
    assert all(q.targets_concern is None for q in questions)


def test_no_obvious_personal_data(questions: list[Question]) -> None:
    for q in questions:
        for text in [q.text, q.purpose, *q.look_for, *q.follow_ups]:
            assert mask_text(text) == text, f"{q.id}: {text}"
