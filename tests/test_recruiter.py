"""Recruiter rules (Backend Schema, "Tela do recrutador: regras") with 0, 2, 3 and 10 sessions."""

from datetime import UTC, datetime, timedelta

import pytest

from mia.recruiter import (
    MIN_SESSIONS_FOR_AVERAGE,
    above_average_rows,
    build_row,
    case_average,
    case_stats,
    is_above_average,
    sort_rows,
)
from mia.schemas import Session

T0 = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)
SECRET_VISITOR = "visitor-secreto-0000"


def completed(n: int, score: float, case_id: str = "caso") -> Session:
    ended = T0 + timedelta(minutes=n)
    return Session(
        visitor_id=f"{SECRET_VISITOR}-{n}",
        session_id=f"01S{n:03d}",
        case_id=case_id,
        candidate_no=n,
        status="completed",
        persona="technical",
        language="pt-BR",
        mode="text",
        overall_score=score,
        headline=f"Headline {n}",
        created_at=T0,
        updated_at=ended,
        ended_at=ended,
    )


def sessions(*scores: float) -> list[Session]:
    return [completed(i + 1, s) for i, s in enumerate(scores)]


def test_threshold_is_three() -> None:
    assert MIN_SESSIONS_FOR_AVERAGE == 3


def test_zero_sessions() -> None:
    assert case_average([]) is None
    assert above_average_rows([]) == []
    stats = case_stats("caso", [])
    assert (stats.completed_sessions, stats.average_score) == (0, None)


def test_two_sessions_list_all_without_average() -> None:
    two = sessions(2.0, 4.0)
    assert case_average(two) is None
    rows = above_average_rows(two)
    assert [r.candidate_no for r in rows] == [2, 1]  # most recent first
    assert all(r.delta_vs_case_avg is None for r in rows)
    assert case_stats("caso", two).average_score is None


def test_three_sessions_keep_only_above_average() -> None:
    three = sessions(2.0, 3.0, 4.0)
    assert case_average(three) == 3.0
    rows = above_average_rows(three)
    assert [(r.candidate_no, r.delta_vs_case_avg) for r in rows] == [(3, 1.0)]
    assert case_stats("caso", three).average_score == 3.0


def test_three_equal_scores_show_nobody() -> None:
    assert above_average_rows(sessions(3.0, 3.0, 3.0)) == []


def test_ten_sessions_filter_and_order() -> None:
    ten = sessions(1.0, 5.0, 2.0, 4.5, 3.0, 4.5, 2.5, 3.5, 1.5, 4.0)
    average = sum([1.0, 5.0, 2.0, 4.5, 3.0, 4.5, 2.5, 3.5, 1.5, 4.0]) / 10  # 3.15
    assert case_average(ten) == pytest.approx(average)
    rows = above_average_rows(ten)
    # 5.0 first; the two 4.5 tie on delta -> most recent (no. 6) before no. 4.
    assert [r.candidate_no for r in rows] == [2, 6, 4, 10, 8]
    assert rows[0].delta_vs_case_avg == round(5.0 - average, 2)
    assert case_stats("caso", ten).average_score == round(average, 2)


def test_rounding_to_two_decimals() -> None:
    three = sessions(3.0, 3.0, 4.0)  # average 3.3333
    assert case_stats("caso", three).average_score == 3.33
    assert above_average_rows(three)[0].delta_vs_case_avg == 0.67


@pytest.mark.parametrize(
    ("score", "average", "expected"),
    [(4.0, 3.0, True), (3.0, 3.0, False), (2.0, 3.0, False), (4.0, None, None), (None, 3.0, False)],
)
def test_is_above_average(
    score: float | None, average: float | None, expected: bool | None
) -> None:
    assert is_above_average(score, average) is expected


def test_sort_rows_without_average_uses_most_recent() -> None:
    rows = [build_row(s, None) for s in sessions(5.0, 1.0, 3.0)]
    assert [r.candidate_no for r in sort_rows(rows)] == [3, 2, 1]


def test_rows_are_anonymous() -> None:
    ten = sessions(*[float(1 + i % 5) for i in range(10)])
    dumped = "".join(r.model_dump_json() for r in above_average_rows(ten))
    dumped += "".join(build_row(s, None).model_dump_json() for s in ten)
    assert SECRET_VISITOR not in dumped
    assert "visitor" not in dumped
    assert set(build_row(ten[0], 3.0).model_dump()) == {
        "session_id",
        "case_id",
        "candidate_no",
        "ended_at",
        "overall_score",
        "delta_vs_case_avg",
        "headline",
    }
