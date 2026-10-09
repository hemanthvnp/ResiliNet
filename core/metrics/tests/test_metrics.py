"""Metric formulas against the hand-worked values B confirmed (Group 1 of
add-metrics-invariants): expected_diamond.json and expected_cases.json."""

import json
from pathlib import Path

import pytest
from pytest import approx

from core.metrics.compute import compute_metrics
from core.model.types import Allocation, DecisionRecord, Flow, Metrics, Snapshot, Topology

HERE = Path(__file__).resolve().parent
FIXTURES = HERE.parents[2] / "fixtures"
DIAMOND = json.loads((HERE / "expected_diamond.json").read_text())
CASES = json.loads((HERE / "expected_cases.json").read_text())["cases"]

TOPOLOGY = Topology.model_validate_json((FIXTURES / "topologies" / "diamond.json").read_bytes())
FLOWS = [Flow(**f) for f in json.loads((FIXTURES / "flows" / "diamond.json").read_text())]


def snapshot(rel):
    return Snapshot.model_validate_json((FIXTURES / rel).read_bytes())


def with_link_down(topo, link_id):
    return topo.model_copy(update={"links": [
        l.model_copy(update={"status": "down"}) if l.id == link_id else l for l in topo.links]})


def record(flow, gap):
    """A minimal decision record carrying only what p0_greedy_gap reads."""
    return DecisionRecord(
        flow_id=flow.id, cls=flow.cls, demand=flow.rate, step=1, failed_links=[], previous=[],
        reference_path=[], reference_status="", attempts=[], delivered=0.0, unserved=0.0,
        cause="NONE", cut=[], maxflow_bound=None, greedy_gap=gap, explanation="")


def assert_metrics(actual: Metrics, expected: dict):
    for field, value in expected.items():
        got = getattr(actual, field)
        if isinstance(value, dict):
            want = {int(k) if field == "dr_by_class" else k: v for k, v in value.items()}
            assert list(got) == sorted(got), f"{field} keys not sorted"
            assert got.keys() == want.keys(), field
            assert got == approx(want, abs=1e-9), field
        elif value is None:
            assert got is None, field
        else:
            assert got == approx(value, abs=1e-9), field


# 1a: healthy diamond, step 0 (the confirmed snapshot fixtures)

@pytest.mark.parametrize("policy", ["S0", "S0-QoS", "S2"])
def test_healthy_diamond(policy):
    snap = snapshot(DIAMOND["healthy"][policy])
    metrics = compute_metrics(TOPOLOGY, FLOWS, snap.allocation, healthy_latency=DIAMOND["healthy_latency"])
    assert metrics == snap.metrics


# 1b: diamond with BD (L7) failed, step 1

@pytest.mark.parametrize("policy", ["S0", "S0-QoS", "S2"])
def test_diamond_with_bd_failed(policy):
    case = DIAMOND["bd_failed"][policy]
    topo = with_link_down(TOPOLOGY, DIAMOND["bd_failed"]["failed_link"])
    by_id = {f.id: f for f in FLOWS}
    metrics = compute_metrics(
        topo, FLOWS, Allocation.model_validate(case["allocation"]),
        previous=snapshot(case["previous"]).allocation,
        affected=case["affected"],
        healthy_latency=DIAMOND["healthy_latency"],
        decisions=[record(by_id[f], g) for f, g in sorted(case["greedy_gap"].items())],
        compute_ms=0.0,
    )
    assert_metrics(metrics, case["expected"])


# 1c: small cases E1 to E7

def run_case(name):
    case = CASES[name]
    return compute_metrics(
        Topology.model_validate(case["topology"]),
        [Flow(**f) for f in case["flows"]],
        Allocation.model_validate(case["allocation"]),
        previous=Allocation.model_validate(case["previous"]) if "previous" in case else None,
        affected=case.get("affected", []),
        healthy_latency=case["healthy_latency"],
    ), case["expected"]


@pytest.mark.parametrize("name", sorted(CASES))
def test_case(name):
    metrics, expected = run_case(name)
    assert_metrics(metrics, expected)


def test_compute_ms_is_passed_through():
    snap = snapshot(DIAMOND["healthy"]["S2"])
    m = compute_metrics(TOPOLOGY, FLOWS, snap.allocation, healthy_latency=DIAMOND["healthy_latency"],
                        compute_ms=12.5)
    assert m.compute_ms == 12.5


def test_step_zero_has_no_recovery_or_churn():
    snap = snapshot(DIAMOND["healthy"]["S0"])
    m = compute_metrics(TOPOLOGY, FLOWS, snap.allocation, healthy_latency=DIAMOND["healthy_latency"])
    assert m.recovery_ratio is None
    assert (m.churn_flows, m.churn_rate) == (0, 0)


def test_same_inputs_give_identical_json():
    snap = snapshot(DIAMOND["healthy"]["S0-QoS"])
    first = compute_metrics(TOPOLOGY, FLOWS, snap.allocation, healthy_latency=DIAMOND["healthy_latency"])
    second = compute_metrics(TOPOLOGY, list(reversed(FLOWS)), snap.allocation,
                             healthy_latency=DIAMOND["healthy_latency"])
    assert first.model_dump_json() == second.model_dump_json()
