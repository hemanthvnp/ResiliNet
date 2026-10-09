"""The seeded benchmark matrix (change add-cli-benchmark, group 3; spec: benchmark).

The matrix runs on a small campus network (3 buildings, 24 flows) so the tests take seconds; the
structure, the determinism and the sizing rule do not depend on the size.
"""

import json
import math
from pathlib import Path

import pytest

from cli import benchmark as bm
from cli.main import main
from core.gen.campus import DEFAULT_TOPOLOGY, DEFAULT_TRAFFIC
from core.gen.registry import resolve_topology
from core.model.types import PolicyConfig

SMALL_TOPOLOGY = DEFAULT_TOPOLOGY.model_copy(update={"buildings": 3})
SMALL_TRAFFIC = DEFAULT_TRAFFIC.model_copy(update={"n_flows": 24})
SEEDS = 2


def run(**kwargs):
    return bm.run_benchmark(SEEDS, processes=1, topology_spec=SMALL_TOPOLOGY, traffic_spec=SMALL_TRAFFIC, **kwargs)


@pytest.fixture(scope="module")
def result():
    return run()


def by(rows, *keys):
    out = {}
    for r in rows:
        out.setdefault(tuple(r[k] for k in keys), []).append(r)
    return out


# --- the matrix (3.1, 3.2) --------------------------------------------------------------


def test_every_policy_for_every_seed_case_and_load_factor(result):
    cells = by([r for r in result.rows if r["variant"] == "default"], "seed", "case", "load_factor")
    assert len(cells) == SEEDS * len(bm.CASES) * len(bm.LOAD_FACTORS)
    for key, rows in cells.items():
        assert [r["policy"] for r in rows] == list(bm.POLICY_ORDER), key


def test_identical_conditions_across_policies(result):
    # Same flows (total demand) and same failed links for every policy of a seed, case and load factor.
    for key, rows in by(result.rows, "seed", "case", "load_factor").items():
        assert len({r["total_demand"] for r in rows}) == 1, key
        assert len({r["failed_links"] for r in rows}) == 1, key


def test_failures_do_not_depend_on_the_load_factor_or_the_policy(result):
    for key, rows in by(result.rows, "seed", "case").items():
        assert len({r["failed_links"] for r in rows}) == 1, key


def test_the_four_cases_fail_what_the_design_says(result):
    rows = by([r for r in result.rows if r["policy"] == "S2" and r["variant"] == "default"], "seed", "case")
    for seed in {r["seed"] for r in result.rows}:
        assert rows[(seed, "healthy")][0]["failed_links"] == ""
        assert rows[(seed, "uplink")][0]["failed_links"] == "L6"
        assert len(rows[(seed, "multi")][0]["failed_links"].split(";")) == 3
        assert rows[(seed, "recovered")][0]["failed_links"] == ""  # failed, then recovered


def test_six_load_factors_per_policy(result):
    default = [r for r in result.rows if r["variant"] == "default"]
    for key, rows in by(default, "seed", "case", "policy").items():
        assert [r["load_factor"] for r in rows] == [0.5, 0.75, 1.0, 1.25, 1.5, 2.0], key


def test_demand_scales_with_the_load_factor(result):
    rows = by([r for r in result.rows if r["policy"] == "S0" and r["case"] == "healthy"], "seed", "load_factor")
    for seed in {r["seed"] for r in result.rows}:
        demand = {f: rows[(seed, f)][0]["total_demand"] for f in bm.LOAD_FACTORS}
        assert demand[0.5] < demand[1.0] < demand[2.0]
        assert abs(demand[2.0] - 2 * demand[1.0]) <= 24  # each of the 24 flows rounds to a whole Mbps


def test_each_ablation_variant_differs_from_the_default_in_exactly_one_knob():
    topology = resolve_topology(SMALL_TOPOLOGY.model_copy(update={"seed": 100})).topology
    options = bm.variants(topology)
    default = options[0][1]
    assert options[0][0] == "default" and default == PolicyConfig()
    assert len(options) == 10  # the default and nine changes
    for label, cfg in options[1:]:
        assert len(bm.changed_knobs(default, cfg)) == 1, label


def test_the_lambda_variants_are_multiples_of_the_mean_link_latency():
    topology = resolve_topology(SMALL_TOPOLOGY.model_copy(update={"seed": 100})).topology
    mean = sum(link.latency for link in topology.links) / len(topology.links)
    lambdas = {label: cfg.congestion_lambda for label, cfg in bm.variants(topology) if label.startswith("lambda")}
    assert lambdas == {f"lambda={k}xmean": round(k * mean) for k in (0.5, 1, 2)}


def test_ablations_are_s2_only_at_the_demo_load_and_one_knob_each(result):
    ablations = [r for r in result.rows if r["variant"] != "default"]
    assert ablations and {r["policy"] for r in ablations} == {"S2"} and {r["load_factor"] for r in ablations} == {1.0}
    assert len(ablations) == SEEDS * len(bm.CASES) * 9
    defaults = PolicyConfig()
    for r in ablations:
        changed = [k for k in bm.CONFIG_COLUMNS if r[k] != getattr(defaults, k)]
        assert len(changed) <= 1, r["variant"]  # a lambda that rounds to 0 changes nothing, and is still one knob


def test_baselines_use_the_default_config(result):
    for r in (r for r in result.rows if r["policy"] != "S2"):
        assert (r["order"], r["max_paths"], r["congestion_lambda"], r["util_cap"]) == ("class_size_desc", 3, 0, 1.0)


# --- results files (3.3) ----------------------------------------------------------------


def test_csv_has_every_column_filled_and_sorted_rows(result, tmp_path):
    csv_path, _ = bm.write_results(result, tmp_path)
    lines = csv_path.read_text(encoding="utf-8").splitlines()
    assert lines[0].split(",") == list(bm.COLUMNS)
    assert len(lines) == len(result.rows) + 1
    for line in lines[1:]:
        cells = line.split(",")
        assert len(cells) == len(bm.COLUMNS)
        assert all(c != "" for i, c in enumerate(cells) if bm.COLUMNS[i] != "failed_links"), line
    read = bm.read_rows(csv_path)
    assert [bm.sort_key(r) for r in read] == sorted(bm.sort_key(r) for r in read)


def test_the_csv_round_trips_to_the_rows(result, tmp_path):
    csv_path, _ = bm.write_results(result, tmp_path)
    for written, read in zip(result.rows, bm.read_rows(csv_path), strict=True):
        for column in bm.COLUMNS:
            a, b = written[column], read[column]
            assert (math.isnan(a) and math.isnan(b)) if isinstance(a, float) and math.isnan(a) else a == b, column


def test_the_summary_records_the_config_the_commit_and_the_reduction(result, tmp_path):
    _, summary_path = bm.write_results(result, tmp_path)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["seeds_run"] == SEEDS and summary["benchmark_seeds"] == [100, 200]
    assert summary["policies"] == list(bm.POLICY_ORDER) and summary["load_factors"] == list(bm.LOAD_FACTORS)
    assert summary["reduction"] == "none" and summary["rows"] == len(result.rows)
    assert len(summary["git"]["commit"]) >= 7 and isinstance(summary["git"]["dirty"], bool)
    assert summary["not_reproducible_columns"] == ["compute_ms"]


ONE_LOAD = {"load_factors": (1.0,)}  # the sweep is covered above; these tests are about something else


def test_a_two_seed_benchmark_is_reproducible():
    first, second = run(**ONE_LOAD), run(**ONE_LOAD)
    assert bm.masked(first.rows) == bm.masked(second.rows)


def test_the_worker_pool_gives_the_same_rows_as_one_process():
    pooled = bm.run_benchmark(SEEDS, processes=2, topology_spec=SMALL_TOPOLOGY, traffic_spec=SMALL_TRAFFIC,
                              **ONE_LOAD)
    assert bm.masked(pooled.rows) == bm.masked(run(**ONE_LOAD).rows)


def test_the_invariants_hold_on_every_snapshot_of_the_matrix():
    checked = run(check=True, **ONE_LOAD)  # raises InvariantError on a violation
    assert checked.summary["check_invariants"] is True


def test_an_unknown_policy_is_rejected_and_named():
    with pytest.raises(ValueError, match="S9"):
        run(policies=("S9",))


# --- sizing the matrix (3.4) ------------------------------------------------------------
# Runs per seed, by hand: 4 cases x (6 load factors x 4 policies = 24) = 96 without ablations; each case adds
# the nine variants for 33, so 132 in all; with only max_paths (3) and lambda (3), 4 x 30 = 120.


def test_runs_per_seed():
    assert bm.runs_per_seed(6, 4, bm.ABLATION_GROUPS) == 132
    assert bm.runs_per_seed(6, 4, ("max_paths", "congestion_lambda")) == 120
    assert bm.runs_per_seed(6, 4, ()) == 96


def test_a_matrix_that_fits_the_budget_is_not_cut():
    # 60 s for the first seed, 30 seeds, one process: 1800 s, exactly the 30 minute budget.
    plan = bm.plan_matrix(30, 60.0, 1)
    assert (plan.seeds, plan.ablation_groups, plan.reduction) == (30, bm.ABLATION_GROUPS, "")
    assert plan.projected_seconds == pytest.approx(1800.0)


def test_processes_divide_the_projection():
    assert bm.plan_matrix(30, 400.0, 8).projected_seconds == pytest.approx(1500.0)  # 400 x 30 / 8


def test_a_projected_overrun_cuts_the_ablations_to_max_paths_and_lambda():
    # 65 s: the full matrix is 65 x 30 = 1950 s, over; without the order and util_cap ablations it is
    # 65 x 30 x 120 / 132 = 1772.7 s, which fits.
    plan = bm.plan_matrix(30, 65.0, 1)
    assert plan.ablation_groups == ("max_paths", "congestion_lambda") and plan.seeds == 30
    assert plan.projected_seconds == pytest.approx(65 * 30 * 120 / 132)
    assert "ablations cut to max_paths and congestion lambda" in plan.reduction
    assert "32.5 min" in plan.reduction  # the 1950 s projection of the full matrix, stated in minutes


def test_a_still_larger_overrun_goes_to_ten_seeds_and_no_ablations():
    # 70 s: 2100 s full, and 70 x 30 x 120 / 132 = 1909 s reduced, both over. Ten seeds without ablations is
    # 70 x 10 x 96 / 132 = 509 s.
    plan = bm.plan_matrix(30, 70.0, 1)
    assert (plan.seeds, plan.ablation_groups) == (10, ())
    assert plan.projected_seconds == pytest.approx(70 * 10 * 96 / 132)
    assert "10 seeds, no ablations" in plan.reduction


def test_fewer_seeds_than_ten_are_not_raised():
    assert bm.plan_matrix(4, 10000.0, 1).seeds == 4


def test_a_projected_overrun_cuts_the_ablations_and_the_summary_says_so():
    # No budget of a billionth of a second can be met, on any machine, so the run falls back to no ablations, and records it.
    cut = run(budget=1e-9, **ONE_LOAD)
    assert cut.summary["reduction"] != "none" and "no ablations" in cut.summary["reduction"]
    assert {r["variant"] for r in cut.rows} == {"default"}
    assert cut.summary["ablation_groups"] == []


def test_the_first_seed_rows_that_the_plan_cuts_are_dropped():
    cut = run(budget=1e-9, **ONE_LOAD)
    assert all(r["variant"] == "default" for r in cut.rows if r["seed"] == bm.benchmark_seed(0))


# --- H4 timing (3.5) --------------------------------------------------------------------


def test_the_median_compute_time_is_a_positive_number_of_milliseconds():
    value = bm.median_compute_ms(3, topology_spec=SMALL_TOPOLOGY, traffic_spec=SMALL_TRAFFIC)
    assert 0 < value < 60_000


# --- the command (3.3) ------------------------------------------------------------------


def test_the_command_writes_the_csv_and_the_summary(tmp_path, capsys):
    argv = ["benchmark", "--seeds", "1", "--buildings", "3", "--flows", "24", "--processes", "1",
            "--out", str(tmp_path / "out")]
    assert main(argv) == 0
    assert (tmp_path / "out" / "benchmark.csv").is_file() and (tmp_path / "out" / "summary.json").is_file()
    assert "132 rows for 1 seeds" in capsys.readouterr().out


def test_the_command_can_skip_the_ablations(tmp_path):
    argv = ["benchmark", "--seeds", "1", "--buildings", "3", "--flows", "24", "--processes", "1",
            "--no-ablations", "--out", str(tmp_path)]
    assert main(argv) == 0
    rows = bm.read_rows(Path(tmp_path) / "benchmark.csv")
    assert len(rows) == 96 and {r["variant"] for r in rows} == {"default"}


# --- the metric columns (3.3) -----------------------------------------------------------


def test_the_class_delivery_columns_are_real_numbers_consistent_with_dr(result):
    # DR is the demand-weighted mean of the per-class DRs, so it lies between the smallest and the largest.
    for r in result.rows:
        present = [r[f"dr_p{c}"] for c in bm.CLASSES if not math.isnan(r[f"dr_p{c}"])]
        assert present and min(present) - 1e-9 <= r["dr"] <= max(present) + 1e-9, r
    heavy = [r for r in result.rows if r["policy"] == "S0" and r["load_factor"] == 2.0 and r["case"] == "uplink"]
    assert any(r["dr_p2"] < 1.0 for r in heavy) or any(r["dr"] < 1.0 for r in heavy)  # overload loses traffic


def test_dr_by_class_is_the_hand_worked_diamond_value_for_a_known_row():
    # On the diamond, S0-QoS under the healthy flows gives P0 10 of 15 and P2 0 of 10: DR 0.4, DR_P0 2/3, DR_P2 0.
    from cli.main import simulate
    from core.sim.scenario import load_fixture

    scenario = load_fixture(Path(__file__).resolve().parents[2] / "fixtures" / "scenarios" / "07_diamond.json").scenario
    _, snapshots = simulate(scenario, "S0-QoS", PolicyConfig())
    flows = scenario.traffic
    row = bm.make_row(1, 1, "healthy", 1.0, "S0-QoS", "default", PolicyConfig(), list(flows), snapshots[0])
    assert (row["dr"], row["dr_p0"], row["dr_p2"]) == pytest.approx((0.4, 2 / 3, 0.0))
    assert math.isnan(row["dr_p1"])  # the diamond has no P1 flow
    assert row["overloaded_arcs"] == 2 and row["total_demand"] == 25
