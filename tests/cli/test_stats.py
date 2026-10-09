"""Mean, median, the seeded bootstrap interval and paired differences (add-cli-benchmark, tasks 4.1 to 4.3).

Expected values are in expected_stats.json, worked by hand from the definitions."""

import json
import math
from pathlib import Path

import pytest

from cli.stats import RESAMPLES, bootstrap_interval, paired_differences, summarize

EXPECTED = json.loads((Path(__file__).parent / "expected_stats.json").read_text(encoding="utf-8"))


def test_mean_and_median_of_the_hand_worked_sample():
    summary = summarize(EXPECTED["sample"]["values"])
    assert (summary.n, summary.mean, summary.median) == (5, EXPECTED["sample"]["mean"], EXPECTED["sample"]["median"])


def test_the_interval_of_a_two_point_sample_is_zero_to_one():
    low, high = bootstrap_interval(EXPECTED["two_point_sample"]["values"])
    assert [low, high] == EXPECTED["two_point_sample"]["interval"]


def test_the_two_point_interval_does_not_depend_on_the_random_seed():
    for seed in (0, 1, 7, 99, 12345):
        assert bootstrap_interval([0, 1], seed=seed) == (0.0, 1.0)


def test_the_interval_ends_are_the_2_5_and_97_5_percent_points():
    # In each sample an end value of the resampled means has a probability of 3.7%: more than 2.5%, less than 5%.
    # So a 95% interval is 0 on the low side for [0, 1, 1] (a 90% interval would give 1/3) and 1 on the high side
    # for [0, 0, 1] (a 90% interval would give 2/3). See expected_stats.json.
    cases = EXPECTED["tail_mass_between_2_5_and_5_percent"]
    assert bootstrap_interval(cases["low_sample"]["values"])[0] == cases["low_sample"]["low"]
    assert bootstrap_interval(cases["high_sample"]["values"])[1] == cases["high_sample"]["high"]
    assert bootstrap_interval(cases["low_sample"]["values"], level=0.90)[0] == pytest.approx(1 / 3)
    assert bootstrap_interval(cases["high_sample"]["values"], level=0.90)[1] == pytest.approx(2 / 3)


def test_the_interval_of_a_constant_sample_is_that_constant():
    low, high = bootstrap_interval(EXPECTED["constant_sample"]["values"])
    assert [low, high] == EXPECTED["constant_sample"]["interval"]


def test_the_interval_is_identical_on_repeat():
    values = [0.31, 0.02, 0.77, 0.5, 0.64, 0.12, 0.9]
    assert bootstrap_interval(values) == bootstrap_interval(values)
    assert summarize(values) == summarize(values)


def test_the_interval_contains_the_mean_and_stays_inside_the_sample_range():
    for values in ([1, 2, 3, 4, 10], [0.1, 0.9, 0.5], [-5, 5, 0, 2, -1, 8]):
        low, high = bootstrap_interval(values)
        mean = math.fsum(values) / len(values)
        assert min(values) <= low <= mean <= high <= max(values)


def test_a_different_seed_gives_a_different_interval_on_a_spread_sample():
    values = [1, 2, 3, 4, 10, 7, 2, 9]
    assert bootstrap_interval(values, seed=1) != bootstrap_interval(values, seed=2)


def test_more_data_gives_a_narrower_interval():
    narrow = bootstrap_interval([0, 1] * 50)
    wide = bootstrap_interval([0, 1] * 2)
    assert narrow[1] - narrow[0] < wide[1] - wide[0]


def test_the_default_is_ten_thousand_resamples_at_95_percent():
    assert RESAMPLES == 10_000


def test_an_empty_sample_has_no_interval():
    with pytest.raises(ValueError):
        bootstrap_interval([])


# --- paired differences (4.3) -----------------------------------------------------------


def seeds(table: dict[str, float]) -> dict[int, float]:
    return {int(k): v for k, v in table.items()}


def test_paired_differences_of_the_hand_worked_seeds():
    got = paired_differences(seeds(EXPECTED["paired"]["a"]), seeds(EXPECTED["paired"]["b"]))
    assert got == pytest.approx(EXPECTED["paired"]["differences"])
    summary = summarize(got)
    assert summary.mean == pytest.approx(EXPECTED["paired"]["mean"])
    assert summary.median == pytest.approx(EXPECTED["paired"]["median"])


def test_paired_differences_are_in_seed_order_whatever_the_dict_order():
    a, b = {3: 0.7, 1: 0.9, 2: 0.8}, {2: 0.6, 3: 0.7, 1: 0.5}
    assert paired_differences(a, b) == pytest.approx([0.4, 0.2, 0.0])


def test_paired_differences_refuse_different_seeds():
    with pytest.raises(ValueError, match="seeds differ"):
        paired_differences({1: 0.5, 2: 0.6}, {1: 0.5, 3: 0.6})


def test_the_paired_interval_is_narrower_than_the_unpaired_one():
    # Two policies that move together across seeds: the per-seed difference is steady, the levels are not.
    s2 = {i: 0.5 + 0.04 * i + 0.1 for i in range(10)}
    base = {i: 0.5 + 0.04 * i for i in range(10)}
    paired = summarize(paired_differences(s2, base))
    unpaired = summarize(list(s2.values()))
    assert paired.high - paired.low < unpaired.high - unpaired.low
    assert paired.mean == pytest.approx(0.1)


def test_the_summary_prints_the_numbers_a_reader_needs():
    text = str(summarize([1, 2, 3, 4, 10]))
    assert "4.0000" in text and "median 3.0000" in text and "n=5" in text and "95% CI" in text
