"""Single-link sensitivity sweep (change criticality-sweep, specs/criticality-sweep/spec.md).

Expected values are the spec's, hand-worked from the PLAN.md section 4 diamond: with any one
link down only one A-D path is left, so S2 delivers F1 10 of 15 and F2 nothing (DR_P0 10/15,
DR 10/25) with no overload, where it delivered 1.00 and 0.80 healthy; S0-QoS ends at the same
values, as healthy, with both flows piled on one path (2 overloaded arcs).
"""

import pytest

from cli.main import load
from core.metrics.invariants import snapshots_identical
from core.model.types import Flow, Link, Node, Scenario, Topology
from core.sim.simulation import Simulation
from ext.__main__ import main
from ext.sweep import bridges, competition_ranks, sweep, sweep_policy

DIAMOND = load("07_diamond")
DIAMOND_LINKS = ["L2", "L5", "L6", "L7"]


def diamond_rows(policy):
    return sweep_policy(lambda p: Simulation(DIAMOND, p, check=True), policy)


# --- fail every link once ----------------------------------------------------

def test_diamond_under_s2():
    rows = diamond_rows("S2")
    assert [r.link_id for r in rows] == DIAMOND_LINKS
    for r in rows:
        assert r.dr_p0 == pytest.approx(10 / 15) and r.dr == pytest.approx(10 / 25)
        assert r.overloaded_arcs == 0
        assert r.dr_p0_drop == pytest.approx(1 - 10 / 15) and r.dr_drop == pytest.approx(0.80 - 0.40)


def test_diamond_under_s0_qos():
    for r in diamond_rows("S0-QoS"):
        assert r.dr_p0 == pytest.approx(10 / 15) and r.dr == pytest.approx(10 / 25)
        assert r.overloaded_arcs == 2
        assert r.dr_p0_drop == pytest.approx(0) and r.dr_drop == pytest.approx(0)


def test_healthy_state_is_restored_between_links():
    made = []

    def new_simulation(policy):
        made.append(Simulation(DIAMOND, policy))
        return made[-1]

    sweep_policy(new_simulation, "S2")
    [sim] = made
    assert snapshots_identical([sim.reset()], [Simulation(DIAMOND, "S2").snapshot])


# --- structural and operational ----------------------------------------------

def test_a_single_link_between_two_nodes_is_structural():
    scenario = Scenario(id="two-node", seed=0, topology={"template": "line"}, events=[], config={},
                       traffic=[Flow(id="F1", src="A", dst="B", rate=10, cls=0)])
    [row] = sweep_policy(lambda p: Simulation(scenario, p, check=True), "S2")
    assert (row.link_id, row.group, row.dr_p0, row.unreachable_demand) == ("L1", "structural", 0, 10)


def test_the_diamond_has_no_bridges():
    assert {r.group for r in diamond_rows("S2")} == {"operational"}


def test_a_parallel_link_is_not_a_bridge():
    nodes = [Node(id="A", type="switch", name="A"), Node(id="B", type="switch", name="B")]
    link = dict(u="A", v="B", capacity=10, latency=1, status="up")
    assert bridges(Topology(nodes=nodes, links=[Link(id="L1", **link)])) == {"L1"}
    assert bridges(Topology(nodes=nodes, links=[Link(id="L1", **link), Link(id="L2", **link)])) == set()


# --- ranking -----------------------------------------------------------------

def test_ties_share_a_rank_and_the_next_rank_skips():
    assert competition_ranks([(0.5, 0.9), (0.5, 0.9), (0.9, 0.9)]) == [1, 1, 3]
    assert competition_ranks([(1.0, 0.8), (0.2, 0.5), (1.0, 0.7)]) == [3, 1, 2]


def test_all_diamond_links_tie_at_rank_1_in_link_id_order():
    rows = diamond_rows("S2")
    assert [(r.rank, r.link_id) for r in rows] == [(1, link) for link in DIAMOND_LINKS]


# --- command and output ------------------------------------------------------

def test_default_run_writes_eight_rows_in_order(tmp_path):
    out = tmp_path / "sweep.csv"
    assert main(["sweep", "--scenario", "07_diamond", "--out", str(out)]) == 0
    header, *rows = out.read_text().splitlines()
    assert header == ("policy,group,rank,link_id,dr_p0,dr,dr_p0_drop,dr_drop,"
                      "overloaded_arcs,unreachable_demand")
    assert [tuple(r.split(",")[:4]) for r in rows] == (
        [("S0-QoS", "operational", "1", link) for link in DIAMOND_LINKS]
        + [("S2", "operational", "1", link) for link in DIAMOND_LINKS])


def test_a_repeat_run_is_byte_identical(tmp_path):
    first, second = tmp_path / "a.csv", tmp_path / "b.csv"
    for out in (first, second):
        assert main(["sweep", "--scenario", "07_diamond", "--out", str(out)]) == 0
    assert first.read_bytes() == second.read_bytes()


def test_unknown_policy_exits_non_zero_and_names_it(capsys):
    assert main(["sweep", "--scenario", "07_diamond", "--policies", "S9"]) != 0
    assert "S9" in capsys.readouterr().err


def test_the_campus_sweep_passes_every_invariant():
    assert main(["sweep", "--scenario", "01_normal", "--check"]) == 0
