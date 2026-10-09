"""Invariant checker against the hand-chosen cases B confirmed (Group 2 of
add-metrics-invariants, K0 to K17). A broken case asserts that the named invariant
is among the violations, as the spec scenarios do; valid snapshots must report none."""

import json
from pathlib import Path

import pytest

from core.metrics.invariants import (
    InvariantError,
    assert_invariants,
    check_invariants,
    class_isolation,
    snapshots_identical,
)
from core.model.ledger import Ledger
from core.model.types import Flow, PolicyConfig, Snapshot, Topology

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"
TOPOLOGY = Topology.model_validate_json((FIXTURES / "topologies" / "diamond.json").read_bytes())
FLOWS = [Flow(**f) for f in json.loads((FIXTURES / "flows" / "diamond.json").read_text())]
FRACTIONAL_FLOWS = [Flow(**f) for f in json.loads((FIXTURES / "flows" / "s0_fractional.json").read_text())]
LATENCY = {"F1": 2, "F2": 2}


def raw(name):
    return json.loads((FIXTURES / "snapshots" / f"{name}.json").read_text())


def check(snap: dict, policy="S2", flows=FLOWS):
    return check_invariants(Snapshot.model_validate(snap), topology=TOPOLOGY, flows=flows,
                            policy=policy, healthy_latency=LATENCY)


def ids(violations):
    return {(v.invariant, v.subject) for v in violations}


def s2():
    return raw("diamond_healthy_s2")


def decision(flow_id="F2", cls=2, cause="INSUFFICIENT_CAPACITY", cut=(), gap=0.0):
    return {"flow_id": flow_id, "cls": cls, "demand": 10, "step": 0, "failed_links": [], "previous": [],
            "reference_path": [], "reference_status": "", "attempts": [], "delivered": 5.0, "unserved": 5.0,
            "cause": cause, "cut": list(cut), "maxflow_bound": 5, "greedy_gap": gap, "explanation": ""}


# K0, K4, K7: valid snapshots report nothing

@pytest.mark.parametrize("name, policy", [
    ("diamond_healthy_s0", "S0"), ("diamond_healthy_s0qos", "S0-QoS"),
    ("diamond_healthy_s1", "S1"), ("diamond_healthy_s2", "S2"),
])
def test_valid_diamond_fixtures(name, policy):
    assert check(raw(name), policy) == []


def test_fractional_s0_fixture_is_valid():  # K4
    assert check(raw("s0_fractional"), "S0", FRACTIONAL_FLOWS) == []


# K1: I1, path through a down arc

def test_down_arc_on_a_path():
    snap = s2()
    snap["link_state"]["L7"] = "down"
    assert ("I1", "F1") in ids(check(snap))


# K2, K3: I2, not a simple path from src to dst

def test_path_visiting_a_node_twice():
    snap = s2()
    snap["allocation"]["results"]["F2"]["paths"][0]["arcs"] = ["L5:A>C", "L5:C>A", "L2:A>B", "L7:B>D"]
    assert ("I2", "F2") in ids(check(snap))


def test_path_ending_at_the_wrong_node():
    snap = s2()
    snap["allocation"]["results"]["F2"]["paths"][0]["arcs"] = ["L5:A>C"]
    assert ("I2", "F2") in ids(check(snap))


# K5: I3, over-delivery

def test_over_delivery():
    snap = s2()
    snap["allocation"]["results"]["F2"].update(delivered=11.0, unserved=-1.0)
    assert ("I3", "F2") in ids(check(snap))


# K6, K7: I4, capacity under S1/S2 only

def test_overloaded_arc_under_s2():
    snap = s2()
    snap["allocation"]["results"]["F1"]["paths"][0]["rate"] = 11
    snap["allocation"]["arc_load"]["L2:A>B"] = 11
    assert ("I4", "L2:A>B") in ids(check(snap))


def test_overload_is_not_an_i4_violation_under_s0():
    violations = check(raw("diamond_healthy_s0"), "S0")
    assert all(v.invariant != "I4" for v in violations)


# K8: I6, arc load mismatch

def test_arc_load_mismatch():
    snap = s2()
    snap["allocation"]["arc_load"]["L5:A>C"] = 9
    assert ("I6", "L5:A>C") in ids(check(snap))


# K9, K10, K11: I7, causes

def test_false_disconnection():
    snap = s2()
    snap["allocation"]["results"]["F2"]["cause"] = "DISCONNECTED"
    assert ("I7", "F2") in ids(check(snap))


def test_unserved_with_no_cause():
    snap = s2()
    snap["allocation"]["results"]["F2"]["cause"] = "NONE"
    assert ("I7", "F2") in ids(check(snap))


def test_insufficient_capacity_when_disconnected():
    snap = s2()
    snap["link_state"].update(L2="down", L5="down")
    assert ("I7", "F2") in ids(check(snap))


# K12: I9, tampered metric

def test_tampered_dr():
    snap = s2()
    snap["metrics"]["dr"] = 0.9
    assert ("I9", "dr") in ids(check(snap))


# K13, K14: I11, explanation consistency

def test_cut_under_path_limit():
    snap = s2()
    snap["decisions"] = [decision(cause="PATH_LIMIT", cut=[{"arc": "L5:A>C", "state": "saturated",
                                                            "load_by_class": {"0": 5, "2": 5}}])]
    assert ("I11", "F2") in ids(check(snap))


def test_negative_greedy_gap():
    snap = s2()
    snap["decisions"] = [decision(gap=-1.0)]
    assert ("I11", "F2") in ids(check(snap))


# K15: I8, determinism comparison

def test_only_compute_time_differs():
    a, b = s2(), s2()
    b["metrics"]["compute_ms"] = 12.5
    assert snapshots_identical([Snapshot.model_validate(a)], [Snapshot.model_validate(b)])


def test_a_metric_differs():
    a, b = s2(), s2()
    b["metrics"]["dr"] = 0.9
    assert not snapshots_identical([Snapshot.model_validate(a)], [Snapshot.model_validate(b)])


def test_sequences_of_different_length_differ():
    assert not snapshots_identical([Snapshot.model_validate(s2())], [])


# K16: I10, class isolation under S2

def test_class_isolation_holds_on_the_diamond():
    from core.routing.registry import get_policy
    assert class_isolation(get_policy("S2"), TOPOLOGY, FLOWS, PolicyConfig()) == []


# K17: I5, ledger symmetry

def test_ledger_reserve_release_is_symmetric():
    ledger = Ledger(TOPOLOGY)
    held = [(["L2:A>B", "L7:B>D"], 10, 0), (["L5:A>C", "L6:C>D"], 5, 0), (["L5:A>C", "L6:C>D"], 5, 2)]
    for path, rate, cls in held:
        ledger.reserve(path, rate, cls)
    for path, rate, cls in reversed(held):
        ledger.release(path, rate, cls)
    assert all(ledger.residual(a) == 10 for a in ledger.arcs)


# Ordering and the raising wrapper

def test_violations_are_sorted_by_invariant_then_subject():
    snap = s2()
    snap["link_state"]["L7"] = "down"
    snap["allocation"]["arc_load"]["L5:A>C"] = 9
    violations = check(snap)
    keys = [(int(v.invariant[1:]), v.subject) for v in violations]
    assert keys == sorted(keys)


def test_assert_invariants_raises_with_every_violation():
    snap = s2()
    snap["metrics"]["dr"] = 0.9
    with pytest.raises(InvariantError, match="I9"):
        assert_invariants(Snapshot.model_validate(snap), topology=TOPOLOGY, flows=FLOWS, policy="S2",
                          healthy_latency=LATENCY)
