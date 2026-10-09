"""PLAN.md section 13 edge cases through the simulation (task 5.1), against the
values B confirmed (Group 3 of add-simulation-engine, X1 to X4), plus the
invariant sweep of task 6.1. Invariant checking is on for every run."""

from pathlib import Path

import pytest
from pytest import approx

from core.model.types import Flow, Link, Node, PolicyConfig, Topology
from core.sim.scenario import load_fixture
from core.sim.simulation import Simulation, run_scenario

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"


def topo(*links, nodes=None):
    names = nodes or sorted({n for l in links for n in (l.u, l.v)})
    return Topology(nodes=[Node(id=n, type="switch", name=n) for n in names], links=list(links))


def link(id, u, v, capacity, latency=1):
    return Link(id=id, u=u, v=v, capacity=capacity, latency=latency, status="up")


def flow(id, src, dst, rate, cls):
    return Flow(id=id, src=src, dst=dst, rate=rate, cls=cls)


def step0(topology, flows, policy):
    return Simulation.from_inputs(topology, flows, policy, PolicyConfig(), check=True).snapshot


def result(snapshot, flow_id):
    r = snapshot.allocation.results[flow_id]
    return [(p.arcs, p.rate) for p in r.paths], r.delivered, r.cause


DIAMOND = topo(link("L2", "A", "B", 10, 1), link("L7", "B", "D", 10, 1),
               link("L5", "A", "C", 10, 2), link("L6", "C", "D", 10, 2))
LINE = topo(link("L1", "A", "B", 10))


def test_two_flows_on_the_same_pair():  # X1
    s = step0(DIAMOND, [flow("F1", "A", "D", 5, 0), flow("F2", "A", "D", 5, 0)], "S2")
    abd = ["L2:A>B", "L7:B>D"]
    assert result(s, "F1") == ([(abd, 5)], 5.0, "NONE")
    assert result(s, "F2") == ([(abd, 5)], 5.0, "NONE")
    assert s.allocation.arc_load["L2:A>B"] == 10


def test_capacity_zero_link():  # X2
    zero = topo(link("L1", "A", "B", 0))
    flows = [flow("F1", "A", "B", 1, 1)]
    s2 = step0(zero, flows, "S2")
    assert result(s2, "F1")[1:] == (0.0, "INSUFFICIENT_CAPACITY")
    s0 = step0(zero, flows, "S0")
    assert result(s0, "F1")[1:] == (0.0, "OVERLOAD_LOSS")
    assert (s0.metrics.overloaded_arcs, s0.metrics.overload_excess) == (1, 1)
    assert s0.metrics.max_util == 0.0


def test_parallel_links():  # X3
    parallel = topo(link("L1", "A", "B", 10, 1), link("L2", "A", "B", 10, 2))
    s = step0(parallel, [flow("F1", "A", "B", 15, 0)], "S2")
    assert result(s, "F1") == ([(["L1:A>B"], 10), (["L2:A>B"], 5)], 15.0, "NONE")


@pytest.mark.parametrize("policy, f1, f2, cause", [
    ("S2", 10.0, 0.0, "INSUFFICIENT_CAPACITY"),
    ("S0-QoS", 10.0, 0.0, "OVERLOAD_LOSS"),
    ("S0", 20 / 3, 10 / 3, "OVERLOAD_LOSS"),
])
def test_p0_saturates_a_bottleneck(policy, f1, f2, cause):  # X4
    s = step0(LINE, [flow("F1", "A", "B", 10, 0), flow("F2", "A", "B", 5, 2)], policy)
    assert s.allocation.results["F1"].delivered == approx(f1, abs=1e-9)
    assert s.allocation.results["F2"].delivered == approx(f2, abs=1e-9)
    assert s.allocation.results["F2"].cause == cause


# Task 6.1: check_invariants on every snapshot of all eight scenarios under all four policies

@pytest.mark.parametrize("policy", ["S0", "S0-QoS", "S1", "S2"])
@pytest.mark.parametrize("path", sorted((FIXTURES / "scenarios").glob("*.json")), ids=lambda p: p.stem)
def test_invariants_hold_on_every_scenario(path, policy):
    snapshots = run_scenario(load_fixture(path).scenario, policy, check=True)
    assert [s.step for s in snapshots] == list(range(len(snapshots)))
