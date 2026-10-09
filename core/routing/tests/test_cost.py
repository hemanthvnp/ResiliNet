import pytest

from core.routing.cost import arc_cost, slope


@pytest.mark.parametrize(
    "load, expected",
    [
        (0, 1),
        (3, 1),    # 3/10 < 1/3
        (4, 3),    # 4/10 >= 1/3
        (6, 3),    # 6/10 < 2/3
        (7, 10),   # 7/10 >= 2/3
        (8, 10),
        (9, 70),   # 9/10 is exactly 0.9
        (10, 70),
    ],
)
def test_slope_on_capacity_10(load, expected):
    assert slope(load, 10) == expected


@pytest.mark.parametrize(
    "load, capacity, expected",
    [(1, 3, 3), (0, 3, 1), (2, 3, 10), (9, 10, 70)],
)
def test_slope_exactly_at_thresholds(load, capacity, expected):
    # 1/3 of 3 and 2/3 of 3 are exact; 0.9 of 10 is exact. No float rounding involved.
    assert slope(load, capacity) == expected


def test_lambda_zero_is_pure_latency_at_any_utilization():
    for load in range(11):
        assert arc_cost(7, load, 10, 0) == 7


def test_cost_adds_lambda_times_slope_minus_one():
    assert arc_cost(2, 0, 10, 4) == 2            # slope 1
    assert arc_cost(2, 5, 10, 4) == 2 + 4 * 2    # slope 3
    assert arc_cost(2, 8, 10, 4) == 2 + 4 * 9    # slope 10
    assert arc_cost(2, 9, 10, 4) == 2 + 4 * 69   # slope 70
