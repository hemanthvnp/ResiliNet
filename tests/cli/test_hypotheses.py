"""Hypotheses H1 to H5 and the report (add-cli-benchmark, task 4.4; spec: benchmark, "Hypothesis evaluation").

The rows are built by hand with differences that can be read off, so every verdict is checked by eye.
"""

import json
import math

import pytest

from cli import benchmark as bm
from cli import hypotheses as hy
from cli.main import main
from cli.report import tables_markdown, write_report
from core.model.types import PolicyConfig


def row(seed, case, load, policy, *, variant="default", dr=1.0, dr_p0=1.0, dr_p1=1.0, overloaded=0, gap=0.0):
    return {"seed": seed, "case": case, "load_factor": load, "policy": policy, "variant": variant, "dr": dr,
            "dr_p0": dr_p0, "dr_p1": dr_p1, "dr_p2": 1.0, "overloaded_arcs": overloaded, "p0_greedy_gap": gap,
            "order": "class_size_desc", "max_paths": 3, "congestion_lambda": 0, "util_cap": 1.0}


def matrix(diffs_pp, *, cases=hy.STRESS_CASES, load=hy.STRESS_LOAD, metric="dr", base=0.80):
    """For each seed i, S0-QoS at `base` and S2 at `base + diffs_pp[i] / 100` on every case, and S0 as S0-QoS."""
    rows = []
    for seed, diff in enumerate(diffs_pp, start=1):
        for case in cases:
            for policy, delta in (("S0", 0.0), ("S0-QoS", 0.0), ("S2", diff / 100)):
                values = {"dr": 1.0, "dr_p0": 1.0}
                values[metric] = base + delta
                rows.append(row(seed, case, load, policy, dr=values["dr"], dr_p0=values["dr_p0"]))
    return rows


# --- H1 ----------------------------------------------------------------------------------


def test_h1_passes_at_exactly_ten_points():
    verdict = hy.h1(matrix([10.0] * 5))
    assert verdict.passed and verdict.detail["mean"] == pytest.approx(10.0)


def test_h1_fails_just_below_ten_points_and_reports_the_measured_value():
    verdict = hy.h1(matrix([9.9] * 5))
    assert not verdict.passed and "+9.90 pp" in verdict.measured


def test_h1_passes_well_above_ten_points():
    assert hy.h1(matrix([25.0, 30.0, 20.0, 22.0, 28.0])).passed


def test_h1_needs_the_interval_above_zero_not_only_the_mean():
    # The mean is exactly 10 points, but a resample can average below 0 (expected_stats.json, h1_mean_ten_...).
    verdict = hy.h1(matrix([40.0, -20.0, 40.0, -20.0]))
    assert verdict.detail["mean"] == pytest.approx(10.0) and verdict.detail["low"] < 0 and not verdict.passed


def test_h1_fails_when_s2_is_worse():
    assert not hy.h1(matrix([-5.0] * 5)).passed


def test_h1_reads_the_stress_cases_at_load_one_only():
    rows = matrix([30.0] * 3) + matrix([0.0] * 3, cases=("healthy",), load=0.5)
    assert hy.h1(rows).passed  # the uncongested rows are not part of H1


def test_h1_averages_the_two_stress_cases_per_seed():
    rows = [row(1, "uplink", 1.0, p, dr=d) for p, d in (("S2", 0.95), ("S0-QoS", 0.80))]
    rows += [row(1, "multi", 1.0, p, dr=d) for p, d in (("S2", 0.85), ("S0-QoS", 0.80))]
    assert hy.paired_points(rows, "dr", hy.STRESS_CASES, 1.0) == pytest.approx([10.0])  # (15 + 5) / 2


def test_a_missing_case_is_an_error_not_a_quiet_average():
    rows = [r for r in matrix([10.0] * 3) if not (r["seed"] == 2 and r["case"] == "multi")]
    with pytest.raises(ValueError, match="lack one of the cases"):
        hy.h1(rows)


# --- H1b ---------------------------------------------------------------------------------


def test_h1b_passes_at_minus_one_point_and_fails_below():
    assert hy.h1b(matrix([-1.0] * 4, metric="dr_p0")).passed
    assert not hy.h1b(matrix([-1.1] * 4, metric="dr_p0")).passed


def test_h1b_passes_when_s2_leads():
    assert hy.h1b(matrix([3.0] * 4, metric="dr_p0")).passed


# --- H2 ----------------------------------------------------------------------------------


def uncongested(dr_diff, p0_diff):
    rows = matrix([dr_diff] * 4, cases=hy.UNCONGESTED_CASES, load=hy.UNCONGESTED_LOAD, metric="dr")
    for r in rows:
        if r["policy"] == "S2":
            r["dr_p0"] = 1.0 + p0_diff / 100
    return rows


def test_h2_passes_within_one_point_on_both_measures():
    assert hy.h2(uncongested(0.5, -0.5)).passed


def test_h2_fails_when_dr_differs_by_more_than_one_point_in_either_direction():
    assert not hy.h2(uncongested(1.1, 0.0)).passed
    assert not hy.h2(uncongested(-1.1, 0.0)).passed


def test_h2_fails_on_dr_p0_alone():
    assert not hy.h2(uncongested(0.0, 1.5)).passed


def test_h2_reads_the_uncongested_cases_at_the_lowest_load_factor():
    assert hy.UNCONGESTED_LOAD == 0.5 and hy.UNCONGESTED_CASES == ("healthy", "recovered")
    rows = uncongested(0.0, 0.0) + matrix([40.0] * 4, cases=hy.UNCONGESTED_CASES, load=1.0)
    assert hy.h2(rows).passed  # a gap at load 1.0 does not count


# --- H3 ----------------------------------------------------------------------------------


def stress_rows(s2_overloaded=0, baseline_overloaded=2):
    rows = []
    for seed in (1, 2):
        for case in hy.STRESS_CASES:
            rows += [row(seed, case, 1.0, "S0", overloaded=baseline_overloaded),
                     row(seed, case, 1.0, "S0-QoS", overloaded=baseline_overloaded),
                     row(seed, case, 1.0, "S2", overloaded=s2_overloaded)]
    return rows


def test_h3_passes_when_only_the_baselines_overload():
    verdict = hy.h3(stress_rows())
    assert verdict.passed and verdict.detail["s2_violations"] == 0
    assert verdict.detail["baseline_stress_rows"] == {"S0": 4, "S0-QoS": 4}


def test_h3_fails_on_a_single_s2_overload_in_any_variant():
    rows = stress_rows() + [row(1, "healthy", 2.0, "S2", variant="max_paths=1", overloaded=1)]
    verdict = hy.h3(rows)
    assert not verdict.passed and verdict.detail["s2_violations"] == 1


def test_h3_reports_but_fails_when_the_baselines_never_overload():
    verdict = hy.h3(stress_rows(baseline_overloaded=0))
    assert not verdict.passed and verdict.detail["baseline_stress_rows"] == {"S0": 0, "S0-QoS": 0}


# --- H4 ----------------------------------------------------------------------------------


def timing(median):
    return {"h4_compute_ms": {"median": median, "repeats": 5, "case": "uplink", "load_factor": 1.0, "policy": "S2"}}


def test_h4_passes_under_a_second_and_fails_at_it():
    assert hy.h4(timing(120.0)).passed and hy.h4(timing(999.9)).passed
    assert not hy.h4(timing(1000.0)).passed


def test_h4_says_when_it_was_not_measured():
    verdict = hy.h4({})
    assert not verdict.passed and "not measured" in verdict.measured


# --- H5 ----------------------------------------------------------------------------------


def s2_runs(non_zero, total=20):
    rows = [row(seed, "uplink", 1.5, "S2") for seed in range(1, total + 1)]
    for r in rows[:non_zero]:
        r["p0_greedy_gap"] = 5.0
    return rows


def test_h5_passes_at_exactly_95_percent_and_lists_the_other_run():
    verdict = hy.h5(s2_runs(1))
    assert verdict.passed and verdict.detail["share_zero"] == pytest.approx(0.95)
    assert verdict.detail["non_zero"] == [{"seed": 1, "case": "uplink", "load_factor": 1.5, "p0_greedy_gap": 5.0}]


def test_h5_fails_below_95_percent_and_lists_every_run_with_a_gap():
    verdict = hy.h5(s2_runs(2))
    assert not verdict.passed and [r["seed"] for r in verdict.detail["non_zero"]] == [1, 2]


def test_h5_counts_only_the_default_s2_runs():
    others = [row(1, "uplink", 1.0, "S2", variant="max_paths=1", gap=9.0), row(1, "uplink", 1.0, "S0", gap=9.0)]
    rows = s2_runs(0) + others
    assert hy.h5(rows).passed


# --- the whole set -----------------------------------------------------------------------


def test_evaluate_reports_all_six_even_when_some_fail():
    rows = matrix([5.0] * 3)  # S2 5 points ahead on the stress cases: H1 fails (below 10)
    for r in rows:
        if r["policy"] != "S2":
            r["overloaded_arcs"] = 2  # the baselines overload, S2 does not: H3 passes
    rows += uncongested(3.0, 0.0) + s2_runs(0)  # 3 points ahead when uncongested: H2 fails; no P0 gap: H5 passes
    verdicts = hy.evaluate(rows, timing(120.0))
    assert [v.id for v in verdicts] == ["H1", "H1b", "H2", "H3", "H4", "H5"]
    passed = {v.id: v.passed for v in verdicts}
    assert passed == {"H1": False, "H1b": True, "H2": False, "H3": True, "H4": True, "H5": True}
    assert all(v.measured for v in verdicts)  # every verdict, failed or not, carries its measured value


# --- the report --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def small_run(tmp_path_factory):
    from core.gen.campus import DEFAULT_TOPOLOGY, DEFAULT_TRAFFIC

    result = bm.run_benchmark(3, processes=1, topology_spec=DEFAULT_TOPOLOGY.model_copy(update={"buildings": 3}),
                              traffic_spec=DEFAULT_TRAFFIC.model_copy(update={"n_flows": 24}))
    directory = tmp_path_factory.mktemp("bench")
    bm.write_results(result, directory)
    return directory


def test_the_summary_records_the_h4_measurement(small_run):
    timing_info = json.loads((small_run / "summary.json").read_text(encoding="utf-8"))["h4_compute_ms"]
    assert timing_info["repeats"] == bm.H4_REPEATS and timing_info["median"] > 0 and timing_info["policy"] == "S2"


def test_the_report_writes_the_tables_and_every_verdict(small_run):
    tables, hypotheses, verdicts = write_report(small_run)
    assert tables.is_file() and hypotheses.is_file() and len(verdicts) == 6
    written = json.loads(hypotheses.read_text(encoding="utf-8"))
    assert [h["id"] for h in written] == ["H1", "H1b", "H2", "H3", "H4", "H5"]
    text = tables.read_text(encoding="utf-8")
    for heading in ("## Hypotheses", "## S2 against S0-QoS, per seed", "## Ablations of S2", "### Case `uplink`"):
        assert heading in text


def test_the_report_is_reproducible_from_the_files(small_run):
    first = write_report(small_run)[0].read_text(encoding="utf-8")
    assert write_report(small_run)[0].read_text(encoding="utf-8") == first


def test_the_report_states_the_commit_the_numbers_came_from(small_run):
    rows = bm.read_rows(small_run / "benchmark.csv")
    summary = json.loads((small_run / "summary.json").read_text(encoding="utf-8"))
    text = tables_markdown(rows, summary, hy.evaluate(rows, summary))
    assert f"commit `{summary['git']['commit'][:10]}`" in text and "3 seeds" in text


def test_the_report_command_prints_the_verdicts(small_run, capsys):
    assert main(["report", "--dir", str(small_run)]) == 0
    out = capsys.readouterr().out
    assert all(f"{h}:" in out for h in ("H1", "H1b", "H2", "H3", "H4", "H5")) and "wrote" in out


def test_the_ablation_table_compares_each_variant_with_the_default(small_run):
    rows = bm.read_rows(small_run / "benchmark.csv")
    from cli.report import ablation_table

    text = ablation_table(rows)
    for variant in ("order=arrival", "max_paths=1", "lambda=2xmean", "util_cap=0.9"):
        assert f"| {variant} |" in text
    assert text.count("| uplink |") == 9


def test_the_ablation_table_says_when_there_are_none():
    from cli.report import ablation_table

    assert ablation_table([row(1, "uplink", 1.0, "S2")]) == "No ablations were run."


def test_a_nan_class_is_not_counted_as_a_delivery(small_run):
    rows = bm.read_rows(small_run / "benchmark.csv")
    assert any(math.isnan(r["recovery_ratio"]) for r in rows)  # no failure, no recovery ratio
    assert PolicyConfig().util_cap == 1.0
