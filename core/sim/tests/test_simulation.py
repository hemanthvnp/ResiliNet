"""Simulation behaviour on the diamond (Group 1 of add-simulation-engine, D1 to D14)
and the scenario fixtures' expect blocks. Expected values are the PLAN.md section 4
table and the metrics Group 1b values, confirmed by B before this code existed."""

import json
from pathlib import Path

import pytest
from pytest import approx

from core.metrics.invariants import InvariantError
from core.model.types import Event, Snapshot
from core.sim.scenario import load_fixture
from core.sim.simulation import Simulation, run_scenario, serialize

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"
SCENARIOS = sorted((FIXTURES / "scenarios").glob("*.json"))
DIAMOND = load_fixture(FIXTURES / "scenarios" / "07_diamond.json").scenario
EXPECTED_METRICS = json.loads(
    (Path(__file__).resolve().parents[2] / "metrics" / "tests" / "expected_diamond.json").read_text())

L7_ARCS = {"L7:B>D", "L7:D>B"}


def fail(*links, node=None):
    return Event(step=1, kind="fail", links=list(links), node=node)


def recover(*links):
    return Event(step=1, kind="recover", links=list(links))


def sim(policy="S2", **kwargs):
    return Simulation(DIAMOND.model_copy(update={"events": []}), policy, check=True, **kwargs)


def arcs_used(snapshot):
    return {a for r in snapshot.allocation.results.values() for p in r.paths for a in p.arcs}


def delivered(snapshot):
    return {f: r.delivered for f, r in sorted(snapshot.allocation.results.items())}


def without_time(snapshot):
    data = json.loads(snapshot.model_dump_json())
    data["metrics"]["compute_ms"] = 0.0
    return data


# D1: step zero

def test_step_zero():
    s = sim().snapshot
    Snapshot.model_validate(s.model_dump())
    assert s.step == 0
    assert sorted(s.allocation.results) == ["F1", "F2"]
    assert sorted(d.flow_id for d in s.decisions) == ["F1", "F2"]


# D2, D3: fail and recover

def test_fail_a_link():
    s = sim().apply(fail("L7"))
    assert s.step == 1
    assert s.link_state["L7"] == "down"
    assert not arcs_used(s) & L7_ARCS


def test_recover_restores_the_step_zero_allocation():
    simulation = sim()
    step0 = simulation.snapshot
    simulation.apply(fail("L7"))
    s = simulation.apply(recover("L7"))
    assert (s.step, s.link_state["L7"]) == (2, "up")
    assert s.allocation == step0.allocation


# D4: affected flows

@pytest.mark.parametrize("policy, affected", [("S0", ["F1", "F2"]), ("S0-QoS", ["F1", "F2"]), ("S2", ["F1"])])
def test_affected_flows(policy, affected):
    simulation = sim(policy)
    assert simulation.apply(fail("L7")).affected_flows == affected
    assert simulation.apply(recover("L7")).affected_flows == []


# D5: idempotent

def test_fail_twice():
    simulation = sim()
    first = simulation.apply(fail("L7"))
    second = simulation.apply(fail("L7"))
    assert second.step == 2
    assert second.allocation == first.allocation
    assert second.affected_flows == []


# D6, D7: atomic events, simultaneous equals sequential

def test_three_links_in_one_event():
    simulation = sim()
    s = simulation.apply(fail("L2", "L5", "L6"))
    assert s.step == 1
    assert all(s.link_state[l] == "down" for l in ("L2", "L5", "L6"))
    for flow in ("F1", "F2"):
        r = s.allocation.results[flow]
        assert (r.delivered, r.cause) == (0.0, "DISCONNECTED")


def test_simultaneous_equals_sequential():
    together = sim().apply(fail("L2", "L5", "L6"))
    seq = sim()
    for link in ("L2", "L5", "L6"):
        last = seq.apply(fail(link))
    assert last.step == 3
    # D7 (corrected, confirmed): the state is equal; fields describing the event differ.
    assert together.link_state == last.link_state
    assert together.allocation == last.allocation
    event_fields = {"recovery_ratio", "churn_flows", "churn_rate", "compute_ms"}
    a, b = together.metrics.model_dump(), last.metrics.model_dump()
    assert {k: v for k, v in a.items() if k not in event_fields} ==         {k: v for k, v in b.items() if k not in event_fields}
    assert (together.affected_flows, last.affected_flows) == (["F1", "F2"], [])
    assert (together.metrics.recovery_ratio, last.metrics.recovery_ratio) == (0.0, None)
    assert (together.metrics.churn_flows, last.metrics.churn_flows) == (2, 0)


# D8: node failure

def test_node_failure():
    s = sim().apply(fail(node="B"))
    assert (s.link_state["L2"], s.link_state["L7"]) == ("down", "down")
    f1, f2 = s.allocation.results["F1"], s.allocation.results["F2"]
    assert (f1.delivered, f1.unserved, f1.cause) == (10.0, 5.0, "INSUFFICIENT_CAPACITY")
    assert (f2.delivered, f2.cause) == (0.0, "INSUFFICIENT_CAPACITY")
    # D8 (corrected, confirmed): same per-flow results as failing L7; arc_load lacks L2's arcs (down).
    only_l7 = sim().apply(fail("L7")).allocation
    assert s.allocation.results == only_l7.results
    assert set(only_l7.arc_load) - set(s.allocation.arc_load) == {"L2:A>B", "L2:B>A"}


# D9: unknown ids

@pytest.mark.parametrize("event", [fail("L99"), fail("L7", "L99"), fail(node="Z")])
def test_unknown_id_changes_nothing(event):
    simulation = sim()
    before = simulation.snapshot
    with pytest.raises(KeyError):
        simulation.apply(event)
    assert simulation.step == 0
    assert simulation.snapshot == before
    assert all(l.status == "up" for l in simulation.topology.links)


# D10: reset

def test_reset_returns_to_step_zero():
    simulation = sim()
    step0 = simulation.snapshot
    simulation.apply(fail("L7"))
    simulation.apply(fail(node="C"))
    assert without_time(simulation.reset()) == without_time(step0)
    assert simulation.step == 0


# D11: reproducible runs (I8)

def test_two_runs_are_byte_identical():
    assert serialize(run_scenario(DIAMOND, "S2")) == serialize(run_scenario(DIAMOND, "S2"))


def test_serialize_masks_compute_time():
    snaps = run_scenario(DIAMOND, "S2")
    assert '"compute_ms": 0.0' in serialize(snaps)


# D12: one policy cannot affect another

def test_policies_get_their_own_copy():
    alone = serialize(run_scenario(DIAMOND, "S2"))
    run_scenario(DIAMOND, "S0")
    assert serialize(run_scenario(DIAMOND, "S2")) == alone


def test_run_returns_one_snapshot_per_step():
    two = DIAMOND.model_copy(update={"events": [fail("L7"), Event(step=2, kind="recover", links=["L7"])]})
    assert [s.step for s in run_scenario(two, "S2")] == [0, 1, 2]


# D13: invariant checking

class OverDelivers:
    name = "S2"

    def route(self, topo, flows, prev, cfg, **kwargs):
        from core.routing.registry import get_policy
        alloc, records = get_policy("S2").route(topo, flows, prev, cfg, **kwargs)
        alloc.results["F2"] = alloc.results["F2"].model_copy(update={"delivered": 11.0, "unserved": -1.0})
        return alloc, records


def test_checking_raises_naming_the_invariant():
    with pytest.raises(InvariantError, match="I3"):
        Simulation(DIAMOND, OverDelivers(), check=True)


# D14: metrics at step 1 equal the confirmed metrics Group 1b

@pytest.mark.parametrize("policy", ["S0", "S0-QoS", "S2"])
def test_step_one_metrics(policy):
    m = run_scenario(DIAMOND, policy)[1].metrics
    for field, value in EXPECTED_METRICS["bd_failed"][policy]["expected"].items():
        got = getattr(m, field)
        if isinstance(value, dict):
            want = {int(k) if field == "dr_by_class" else k: v for k, v in value.items()}
            assert got == approx(want, abs=1e-9), field
        else:
            assert got == approx(value, abs=1e-9), field


# Scenario fixtures: every expect block (Groups 1 and 2, confirmed by B; all four members agreed)

def _metric_matches(metrics, want):
    for field, value in want.items():
        got = getattr(metrics, field)
        if isinstance(value, dict):
            value = {int(k) if field == "dr_by_class" else k: v for k, v in value.items()}
            assert got.keys() == value.keys(), field
        assert got == approx(value, abs=1e-9), field


def _state_metrics(snapshot):
    event_fields = {"recovery_ratio", "churn_flows", "churn_rate", "compute_ms"}
    return {k: v for k, v in snapshot.metrics.model_dump().items() if k not in event_fields}


@pytest.mark.parametrize("path", SCENARIOS, ids=lambda p: p.stem)
def test_scenario_fixture(path):
    fixture = load_fixture(path)
    expect, scenario = fixture.expect, fixture.scenario
    runs = {}

    def run(policy):
        if policy not in runs:
            runs[policy] = run_scenario(scenario, policy, check=True)
        return runs[policy]

    for policy, steps in expect.get("delivered", {}).items():
        assert len(run(policy)) == len(steps), policy
        for snap, want in zip(run(policy), steps):
            assert delivered(snap) == approx({f: float(v) for f, v in want.items()}, abs=1e-9), (policy, snap.step)
    for policy, steps in expect.get("metrics", {}).items():
        for snap, want in zip(run(policy), steps):
            _metric_matches(snap.metrics, want)
    for policy, steps in expect.get("paths", {}).items():
        for snap, want in zip(run(policy), steps):
            for flow, paths in want.items():
                assert [[p.arcs, p.rate] for p in snap.allocation.results[flow].paths] == paths, (policy, flow)
    for policy, steps in expect.get("causes", {}).items():
        for snap, want in zip(run(policy), steps):
            for flow, cause in want.items():
                assert snap.allocation.results[flow].cause == cause, (policy, flow)
    for policy, steps in expect.get("affected", {}).items():
        assert [s.affected_flows for s in run(policy)] == steps, policy
    for policy, steps in expect.get("decisions", {}).items():
        for snap, want in zip(run(policy), steps):
            records = {d.flow_id: d for d in snap.decisions}
            for flow, fields in want.items():
                got = json.loads(records[flow].model_dump_json())
                for field, value in fields.items():
                    assert got[field] == value, (policy, flow, field)
    for policy in expect.get("final_equals_step0", []):
        snaps = run(policy)
        assert snaps[-1].allocation == snaps[0].allocation, policy
    for policy in expect.get("simultaneous_equals_sequential", []):
        together = run(policy)[-1]
        split = [Event(step=i + 1, kind=e.kind, links=[link]) for e in scenario.events
                 for i, link in enumerate(sorted(e.links))]
        sequential = run_scenario(scenario.model_copy(update={"events": split}), policy, check=True)[-1]
        assert together.link_state == sequential.link_state, policy
        assert together.allocation == sequential.allocation, policy
        assert _state_metrics(together) == _state_metrics(sequential), policy


def test_every_expect_key_is_understood():
    known = {"source", "delivered", "metrics", "paths", "causes", "affected", "decisions",
             "final_equals_step0", "simultaneous_equals_sequential"}
    for path in SCENARIOS:
        assert set(load_fixture(path).expect) <= known, path.name


def test_all_eight_scenarios_exist():
    assert [p.stem[:2] for p in SCENARIOS] == ["01", "02", "03", "04", "05", "06", "07", "08"]


# 3.2: the same scenario in two fresh processes

def test_two_fresh_processes_give_identical_output():
    import subprocess
    import sys
    code = ("from core.sim.simulation import run_scenario, serialize; "
            "import sys; sys.stdout.write(serialize(run_scenario(sys.argv[1], 'S2')))")
    path = str(FIXTURES / "scenarios" / "07_diamond.json")
    outs = [subprocess.run([sys.executable, "-c", code, path], capture_output=True, text=True, check=True).stdout
            for _ in range(2)]
    assert outs[0] == outs[1] and outs[0]


# Loader (task 1.2)

def test_generator_scenario_loads_the_generated_network():
    from core.gen.campus import DEFAULT_TOPOLOGY, DEFAULT_TRAFFIC
    from core.gen.registry import resolve_inputs
    scenario = {"id": "gen", "seed": 1, "topology": DEFAULT_TOPOLOGY.model_dump(),
                "traffic": DEFAULT_TRAFFIC.model_dump(), "events": [], "config": {}}
    resolved, flows = resolve_inputs(DEFAULT_TOPOLOGY, DEFAULT_TRAFFIC)
    simulation = Simulation(scenario, "S2")
    assert simulation.topology == resolved.topology
    assert simulation.flows == flows
    assert simulation.effective_seed == resolved.seed


def test_flow_with_unknown_node_is_rejected():
    bad = DIAMOND.model_copy(update={"traffic": [{"id": "F9", "src": "Z", "dst": "D", "rate": 1, "cls": 0}]})
    with pytest.raises(ValueError, match="F9"):
        Simulation(bad, "S2")
