"""Smoke test for the ablation module, so it keeps running as the routing code changes."""

import pytest

from core.routing.tests import ablation


def test_every_setting_changes_exactly_one_knob_from_the_default():
    cfgs = ablation.settings(mean_latency=2.0)
    default = cfgs["default"]
    assert default == ablation.BASE
    for label, cfg in cfgs.items():
        if label != "default":
            assert sum(cfg[k] != default[k] for k in default) == 1, label
    assert cfgs["lambda=2xmean(4)"]["congestion_lambda"] == 4


@pytest.fixture(scope="module")
def rows():
    # One small network at the lightest load, without the process pool.
    return ablation.run_seed((100, 0.5))


def test_run_seed_covers_both_scenarios_and_every_setting(rows):
    labels = {r["cfg"] for r in rows}
    assert len(labels) == 10 and {r["scen"] for r in rows} == set(ablation.SCENARIOS)
    assert len(rows) == 2 * len(labels)


def test_default_s2_keeps_p0_whole_and_is_not_slow(rows):
    for r in (r for r in rows if r["cfg"] == "default"):
        assert r["dr0"] == pytest.approx(1.0) and r["gap0"] == 0
        assert r["ms"] < 1000  # PLAN.md H4: under a second at 50 nodes and 200 flows


def test_one_path_loses_delivery_against_three(rows):
    by = {(r["scen"], r["cfg"]): r for r in rows}
    assert by[("uplink_failed", "max_paths=1")]["dr"] < by[("uplink_failed", "default")]["dr"]


def test_report_has_a_row_per_setting(rows):
    text = ablation.report(rows)  # one seed: the intervals are degenerate but the tables must render
    assert text.count("| max_paths=1 |") == len(ablation.SCENARIOS)
    assert text.count("| util_cap=0.9 |") == len(ablation.SCENARIOS)
