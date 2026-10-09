"""ECMP-style baselines (change ecmp-baseline, specs/ecmp-routing/spec.md).

Expected values are the spec's, hand-worked in PLAN-CYCLE2.md sections 3.1 and 10 and
re-worked for this change: on the square, 15 Mbps splits 8 and 7 and 10 splits 5 and 5, so
the arcs via B carry 13 and via C carry 12. Under strict priority, F2 gets (10 - 8) / 5 of
its 5 via B and (10 - 7) / 5 of its 5 via C, that is 2 + 3. On eight routes of capacity 10,
100 Mbps splits 13 x 4 + 12 x 4, and each route delivers 10.
"""

import json
from fractions import Fraction
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from cli.main import load
from core.metrics.invariants import snapshots_identical
from core.model.types import Flow, Link, Node, PolicyConfig, Scenario, Topology
from core.routing.registry import get_policy
from core.sim.scenario import load_scenario
from core.sim.simulation import Simulation, run_scenario
from ext.__main__ import main
from ext.ecmp import Ecmp, EcmpQoS, ecmp_paths
from core.model.arcs import available_arcs

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples"


def topology(links, nodes=None):
    nodes = nodes or sorted({n for _, u, v, *_ in links for n in (u, v)})
    return Topology(nodes=[Node(id=n, type="switch", name=n) for n in nodes],
                    links=[Link(id=i, u=u, v=v, capacity=c, latency=l, status="up") for i, u, v, c, l in links])


def flow(fid, src, dst, rate, cls=0):
    return Flow(id=fid, src=src, dst=dst, rate=rate, cls=cls)


def paths_of(topo, f):
    return {tuple(p.arcs): p.rate for p in ecmp_paths(available_arcs(topo), f)}


def route(policy, topo, flows):
    return policy.route(topo, flows, None, PolicyConfig())[0]


SQUARE = topology([("L1", "A", "B", 10, 1), ("L2", "B", "D", 10, 1), ("L3", "A", "C", 10, 1), ("L4", "C", "D", 10, 1)])
SQUARE_FLOWS = [flow("F1", "A", "D", 15, 0), flow("F2", "A", "D", 10, 2)]
EIGHT = topology([(f"L{2*i-1}", "S", f"R{i}", 10, 1) for i in range(1, 9)] + [(f"L{2*i}", f"R{i}", "T", 10, 1) for i in range(1, 9)])


# --- equal-cost next hops ----------------------------------------------------

def test_two_next_hops_on_the_square():
    assert paths_of(SQUARE, flow("F", "A", "D", 2)) == {("L1:A>B", "L2:B>D"): 1, ("L3:A>C", "L4:C>D"): 1}


def test_single_shortest_path_on_the_diamond():
    diamond = load("07_diamond")
    alloc = Simulation(diamond, "ECMP").snapshot.allocation
    for f in ("F1", "F2"):
        assert [p.arcs for p in alloc.results[f].paths] == [["L2:A>B", "L7:B>D"]]
    assert (alloc.arc_load["L2:A>B"], alloc.arc_load["L7:B>D"]) == (25, 25)


def test_a_disconnected_flow_has_no_paths():
    topo = topology([("L1", "A", "B", 10, 1)], nodes=["A", "B", "C"])
    result = route(Ecmp(), topo, [flow("F1", "A", "C", 5)]).results["F1"]
    assert (result.paths, result.delivered, result.cause) == ([], 0, "DISCONNECTED")


# --- integer split per next hop ----------------------------------------------

def test_odd_rate_on_the_square():
    assert paths_of(SQUARE, flow("F", "A", "D", 15)) == {("L1:A>B", "L2:B>D"): 8, ("L3:A>C", "L4:C>D"): 7}


def test_shared_first_hop():
    topo = topology([("L1", "S", "A", 100, 1), ("L2", "A", "X", 100, 1), ("L3", "X", "D", 100, 1),
                     ("L4", "A", "Y", 100, 1), ("L5", "Y", "D", 100, 1), ("L6", "S", "B", 100, 1),
                     ("L7", "B", "D", 100, 2)])
    assert paths_of(topo, flow("F", "S", "D", 120)) == {
        ("L1:S>A", "L2:A>X", "L3:X>D"): 30, ("L1:S>A", "L4:A>Y", "L5:Y>D"): 30, ("L6:S>B", "L7:B>D"): 60}
    load = route(Ecmp(), topo, [flow("F", "S", "D", 120)]).arc_load
    assert {a: load[a] for a in ["L1:S>A", "L6:S>B", "L7:B>D", "L2:A>X", "L3:X>D", "L4:A>Y", "L5:Y>D"]} == {
        "L1:S>A": 60, "L6:S>B": 60, "L7:B>D": 60, "L2:A>X": 30, "L3:X>D": 30, "L4:A>Y": 30, "L5:Y>D": 30}


def test_eight_next_hops_at_one_node():
    rates = {p[0].split(">")[1]: r for p, r in paths_of(EIGHT, flow("F", "S", "T", 100)).items()}
    assert rates == {"R1": 13, "R2": 13, "R3": 13, "R4": 13, "R5": 12, "R6": 12, "R7": 12, "R8": 12}


# --- delivery ----------------------------------------------------------------

def test_ecmp_on_the_square():
    alloc = route(Ecmp(), SQUARE, SQUARE_FLOWS)
    assert (alloc.arc_load["L1:A>B"], alloc.arc_load["L2:B>D"], alloc.arc_load["L3:A>C"], alloc.arc_load["L4:C>D"]) == (13, 13, 12, 12)
    assert alloc.results["F1"].delivered == pytest.approx(float(Fraction(80, 13) + Fraction(70, 12)), abs=1e-9)
    assert alloc.results["F2"].delivered == pytest.approx(float(Fraction(50, 13) + Fraction(50, 12)), abs=1e-9)
    assert alloc.results["F1"].cause == "OVERLOAD_LOSS"
    metrics = Simulation(load_scenario(EXAMPLES / "square.json"), "ECMP", check=True).snapshot.metrics
    assert (metrics.dr, metrics.overloaded_arcs) == (pytest.approx(0.80), 4)


def test_ecmp_qos_on_the_square():
    alloc = route(EcmpQoS(), SQUARE, SQUARE_FLOWS)
    assert alloc.results["F1"].delivered == 15 and alloc.results["F2"].delivered == 5
    metrics = Simulation(load_scenario(EXAMPLES / "square.json"), "ECMP-QoS", check=True).snapshot.metrics
    assert (metrics.dr, metrics.dr_by_class[0], metrics.overloaded_arcs) == (pytest.approx(0.80), 1.0, 4)


@pytest.mark.parametrize("ecmp, baseline", [("ECMP", "S0"), ("ECMP-QoS", "S0-QoS")])
def test_on_the_diamond_ecmp_equals_its_baseline(ecmp, baseline):
    diamond = load("07_diamond")
    for a, b in zip(run_scenario(diamond, ecmp, check=True), run_scenario(diamond, baseline)):
        assert {f: r.delivered for f, r in a.allocation.results.items()} == \
               {f: r.delivered for f, r in b.allocation.results.items()}


def test_eight_parallel_routes_ecmp_qos_can_beat_s2():
    scenario = load_scenario(EXAMPLES / "eight-paths.json")
    qos = Simulation(scenario, "ECMP-QoS", check=True).snapshot
    assert qos.allocation.results["F1"].delivered == 80
    assert (qos.metrics.overloaded_arcs, qos.metrics.overload_excess) == (16, 40)
    s0q = Simulation(scenario, "S0-QoS", check=True).snapshot
    assert (s0q.allocation.results["F1"].delivered, s0q.metrics.overloaded_arcs) == (10, 2)
    s2 = Simulation(scenario, "S2", check=True).snapshot
    f1 = s2.allocation.results["F1"]
    [record] = s2.decisions
    assert (f1.delivered, f1.unserved, f1.cause, s2.metrics.overloaded_arcs) == (30, 70, "PATH_LIMIT", 0)
    assert record.greedy_gap == 50
    s2_8 = Simulation(scenario, "S2", PolicyConfig(max_paths=8), check=True).snapshot
    assert (s2_8.allocation.results["F1"].delivered, s2_8.metrics.overloaded_arcs) == (80, 0)


# --- registered, pure, deterministic -----------------------------------------

def test_the_examples_validate():
    for name in ("square", "shared-prefix", "eight-paths"):
        load_scenario(EXAMPLES / f"{name}.json")


def test_compare_includes_ecmp(capsys):
    assert main(["compare", "--scenario", str(EXAMPLES / "square.json"), "--policies", "S0-QoS", "ECMP-QoS", "S2"]) == 0
    rows = [line.split() for line in capsys.readouterr().out.splitlines()[1:]]
    assert [(r[1], r[2]) for r in rows] == [("S0-QoS", "0.400"), ("ECMP-QoS", "0.800"), ("S2", "0.800")]


def test_a_repeat_run_gives_equal_allocations():
    assert route(EcmpQoS(), SQUARE, SQUARE_FLOWS) == route(EcmpQoS(), SQUARE, SQUARE_FLOWS)
    assert get_policy("ECMP").name == "ECMP" and get_policy("ECMP-QoS").name == "ECMP-QoS"


@settings(derandomize=True, max_examples=20, deadline=None,
          suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
@given(seed=st.integers(0, 10_000), buildings=st.integers(2, 8), n_flows=st.integers(1, 30),
       fail=st.lists(st.integers(1, 20), max_size=3, unique=True))
def test_invariants_on_random_campus_scenarios(seed, buildings, n_flows, fail):
    scenario = Scenario(
        id="property", seed=seed, config=PolicyConfig(),
        topology={"generator": "campus", "buildings": buildings, "redundancy": 0.5, "seed": seed},
        traffic={"generator": "campus", "n_flows": n_flows, "load_factor": 1.0,
                 "class_mix": {0: 0.2, 1: 0.3, 2: 0.5}, "seed": seed},
        events=[{"step": 1, "kind": "fail", "links": [f"L{i}" for i in sorted(fail)]}] if fail else [])
    try:
        for policy in ("ECMP", "ECMP-QoS"):
            first = run_scenario(scenario, policy, check=True)  # every invariant; I4 is skipped for baselines
            assert snapshots_identical(first, run_scenario(scenario, policy)), f"{policy}: runs differ"
    except RuntimeError:
        return  # no seed passes the generator's path check at this size; nothing to route
    except (AssertionError, KeyError) as err:
        raise AssertionError(f"{err}\nreplay: seed={seed} buildings={buildings} n_flows={n_flows} fail={fail}") from err


@pytest.mark.parametrize("policy", ["ECMP", "ECMP-QoS"])
def test_invariants_on_the_campus_template_with_the_uplink_failed(policy):
    run_scenario(load("02_uplink_failure"), policy, check=True)
