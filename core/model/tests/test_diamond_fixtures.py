"""Diamond fixtures against the hand-worked values confirmed by B (Group 2).

Source: PLAN.md section 4 (diamond and its table), section 5 (S1 and S2 placement,
greedy gap) and section 8 (metric formulas). Expected values were derived and
confirmed before the fixtures were written; they are never read from code.
"""

import json
from pathlib import Path

import pytest
from pytest import approx

from core.model.types import Flow, Snapshot, Topology

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"

ABD = ["L2:A>B", "L7:B>D"]
ACD = ["L5:A>C", "L6:C>D"]
ARCS = ["L2:A>B", "L2:B>A", "L5:A>C", "L5:C>A", "L6:C>D", "L6:D>C", "L7:B>D", "L7:D>B"]


def load_snapshot(policy):
    return Snapshot.model_validate_json((FIXTURES / "snapshots" / f"diamond_healthy_{policy}.json").read_bytes())


# 2a, 2b: inputs

def test_topology():
    topo = Topology.model_validate_json((FIXTURES / "topologies" / "diamond.json").read_bytes())
    assert sorted(n.id for n in topo.nodes) == ["A", "B", "C", "D"]
    links = {l.id: (l.u, l.v, l.capacity, l.latency, l.status) for l in topo.links}
    assert links == {
        "L2": ("A", "B", 10, 1, "up"),
        "L7": ("B", "D", 10, 1, "up"),
        "L5": ("A", "C", 10, 2, "up"),
        "L6": ("C", "D", 10, 2, "up"),
    }


def test_flows():
    flows = [Flow.model_validate(f) for f in json.loads((FIXTURES / "flows" / "diamond.json").read_text())]
    assert [(f.id, f.src, f.dst, f.rate, f.cls) for f in flows] == [
        ("F1", "A", "D", 15, 0),
        ("F2", "A", "D", 10, 2),
    ]


# 2d: routing results per policy

RESULTS = {
    "s0": {
        "F1": ([(ABD, 15)], 6, 9, "OVERLOAD_LOSS"),
        "F2": ([(ABD, 10)], 4, 6, "OVERLOAD_LOSS"),
    },
    "s0qos": {
        "F1": ([(ABD, 15)], 10, 5, "OVERLOAD_LOSS"),
        "F2": ([(ABD, 10)], 0, 10, "OVERLOAD_LOSS"),
    },
    "s1": {
        "F1": ([(ABD, 10)], 10, 5, "PATH_LIMIT"),
        "F2": ([(ACD, 10)], 10, 0, "NONE"),
    },
    "s2": {
        "F1": ([(ABD, 10), (ACD, 5)], 15, 0, "NONE"),
        "F2": ([(ACD, 5)], 5, 5, "INSUFFICIENT_CAPACITY"),
    },
}

ARC_LOAD = {
    "s0": {"L2:A>B": 25, "L7:B>D": 25},
    "s0qos": {"L2:A>B": 25, "L7:B>D": 25},
    "s1": {"L2:A>B": 10, "L7:B>D": 10, "L5:A>C": 10, "L6:C>D": 10},
    "s2": {"L2:A>B": 10, "L7:B>D": 10, "L5:A>C": 10, "L6:C>D": 10},
}


@pytest.mark.parametrize("policy", sorted(RESULTS))
def test_flow_results(policy):
    results = load_snapshot(policy).allocation.results
    assert sorted(results) == ["F1", "F2"]
    for flow_id, (paths, delivered, unserved, cause) in RESULTS[policy].items():
        r = results[flow_id]
        assert r.flow_id == flow_id
        assert [(p.arcs, p.rate) for p in r.paths] == paths
        assert r.delivered == approx(delivered, abs=1e-9)
        assert r.unserved == approx(unserved, abs=1e-9)
        assert r.cause == cause


@pytest.mark.parametrize("policy", sorted(ARC_LOAD))
def test_arc_load_lists_every_available_arc(policy):  # convention C1
    arc_load = load_snapshot(policy).allocation.arc_load
    assert sorted(arc_load) == ARCS
    assert arc_load == {a: ARC_LOAD[policy].get(a, 0) for a in ARCS}


# 2e: metrics at step 0

METRICS = {
    "s0": dict(
        dr=0.4, dr_by_class={0: 0.4, 2: 0.4}, dr_reach=0.4,
        unserved_by_cause={"OVERLOAD_LOSS": 15},
        overloaded_arcs=2, overload_excess=30, max_util=2.5, mean_util=0.625, arcs_above_90=2,
        link_util={"L2": 2.5, "L7": 2.5, "L5": 0.0, "L6": 0.0},
        latency_stretch=1.0, p0_greedy_gap=0.0,
    ),
    "s0qos": dict(
        dr=0.4, dr_by_class={0: 2 / 3, 2: 0.0}, dr_reach=0.4,
        unserved_by_cause={"OVERLOAD_LOSS": 15},
        overloaded_arcs=2, overload_excess=30, max_util=2.5, mean_util=0.625, arcs_above_90=2,
        link_util={"L2": 2.5, "L7": 2.5, "L5": 0.0, "L6": 0.0},
        latency_stretch=1.0, p0_greedy_gap=0.0,
    ),
    "s1": dict(
        dr=0.8, dr_by_class={0: 2 / 3, 2: 1.0}, dr_reach=0.8,
        unserved_by_cause={"PATH_LIMIT": 5},
        overloaded_arcs=0, overload_excess=0, max_util=1.0, mean_util=0.5, arcs_above_90=4,
        link_util={"L2": 1.0, "L7": 1.0, "L5": 1.0, "L6": 1.0},
        latency_stretch=1.5, p0_greedy_gap=5.0,
    ),
    "s2": dict(
        dr=0.8, dr_by_class={0: 1.0, 2: 0.5}, dr_reach=0.8,
        unserved_by_cause={"INSUFFICIENT_CAPACITY": 5},
        overloaded_arcs=0, overload_excess=0, max_util=1.0, mean_util=0.5, arcs_above_90=4,
        link_util={"L2": 1.0, "L7": 1.0, "L5": 1.0, "L6": 1.0},
        latency_stretch=1.5, p0_greedy_gap=0.0,
    ),
}


@pytest.mark.parametrize("policy", sorted(METRICS))
def test_metrics(policy):
    m = load_snapshot(policy).metrics
    for field, expected in METRICS[policy].items():
        actual = getattr(m, field)
        if isinstance(expected, dict):
            assert actual.keys() == expected.keys(), field  # conventions C2, C3
            assert actual == approx(expected, abs=1e-9), field
        else:
            assert actual == approx(expected, abs=1e-9), field
    # Step 0: nothing affected, nothing moved; compute_ms is masked to 0 (C7).
    assert m.recovery_ratio is None
    assert m.churn_flows == 0 and m.churn_rate == 0
    assert m.compute_ms == 0.0


@pytest.mark.parametrize("policy", sorted(METRICS))
def test_snapshot_header(policy):
    s = load_snapshot(policy)
    assert s.step == 0
    assert s.link_state == {"L2": "up", "L5": "up", "L6": "up", "L7": "up"}
    assert s.affected_flows == []
    if policy != "s1":
        assert s.decisions == []  # convention C6
        return
    # S1 carries its records so p0_greedy_gap recomputes (I9); fixture change agreed by A, B, C, D.
    records = {d.flow_id: d for d in s.decisions}
    assert sorted(records) == ["F1", "F2"]
    f1, f2 = records["F1"], records["F2"]
    assert (f1.cause, f1.delivered, f1.unserved, f1.maxflow_bound, f1.greedy_gap, f1.cut) ==         ("PATH_LIMIT", 10.0, 5.0, 15, 5.0, [])
    assert [(a.arcs, a.cost, a.bottleneck, a.pushed) for a in f1.attempts] == [(ABD, 2, 10, 10)]
    assert (f2.cause, f2.delivered, f2.unserved, f2.maxflow_bound, f2.greedy_gap) == ("NONE", 10.0, 0.0, None, None)
    assert [(a.arcs, a.cost, a.bottleneck, a.pushed) for a in f2.attempts] == [(ACD, 4, 10, 10)]


# Group 3: S0 non-integer fixture (PLAN.md section 4, "a 7 Mbps flow scaled by 0.4")

def test_s0_fractional_flows():
    flows = [Flow.model_validate(f) for f in json.loads((FIXTURES / "flows" / "s0_fractional.json").read_text())]
    assert [(f.id, f.src, f.dst, f.rate, f.cls) for f in flows] == [
        ("F1", "A", "D", 18, 0),
        ("F2", "A", "D", 7, 2),
    ]


def test_s0_fractional_snapshot():
    s = Snapshot.model_validate_json((FIXTURES / "snapshots" / "s0_fractional.json").read_bytes())
    f1, f2 = s.allocation.results["F1"], s.allocation.results["F2"]
    assert [(p.arcs, p.rate) for p in f1.paths] == [(ABD, 18)]
    assert [(p.arcs, p.rate) for p in f2.paths] == [(ABD, 7)]
    assert f2.delivered == approx(2.8, abs=1e-9)
    assert f2.unserved == approx(4.2, abs=1e-9)
    assert f1.delivered == approx(7.2, abs=1e-9)
    assert f1.unserved == approx(10.8, abs=1e-9)
    assert f1.cause == f2.cause == "OVERLOAD_LOSS"
    assert s.allocation.arc_load == {a: {"L2:A>B": 25, "L7:B>D": 25}.get(a, 0) for a in ARCS}

    m = s.metrics
    assert m.dr == approx(0.4, abs=1e-9)
    assert m.dr_by_class == approx({0: 0.4, 2: 0.4}, abs=1e-9)
    assert m.dr_reach == approx(0.4, abs=1e-9)
    assert m.unserved_by_cause == approx({"OVERLOAD_LOSS": 15.0}, abs=1e-9)
    assert (m.overloaded_arcs, m.overload_excess, m.arcs_above_90) == (2, 30, 2)
    assert m.max_util == approx(2.5) and m.mean_util == approx(0.625)
    assert m.link_util == approx({"L2": 2.5, "L7": 2.5, "L5": 0.0, "L6": 0.0})
    assert m.latency_stretch == approx(1.0)
    assert m.recovery_ratio is None
    assert (m.churn_flows, m.churn_rate, m.p0_greedy_gap, m.compute_ms) == (0, 0, 0.0, 0.0)
    assert (s.step, s.affected_flows, s.decisions) == (0, [], [])
