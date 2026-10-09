"""Property tests: random campus networks and event lists, every invariant on every snapshot
(change add-cli-benchmark, tasks 1.2 to 1.4; design: "Property tests call B's checker").

No invariant is defined here. Per snapshot, Simulation(check=True) runs B's checker
(I1 to I4, I6, I7, I9, I11); I8 is snapshots_identical over two runs; I10 is class_isolation,
which PLAN.md section 9 states for S2. I5 is a ledger property, tested in core/model.

A failure ends with a `replay: check_case(Case(...))` line: paste it after the imports
below to rerun exactly that case.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from hypothesis import HealthCheck, given, reject, settings
from hypothesis import strategies as st

from core.gen.registry import resolve_inputs
from core.metrics.invariants import InvariantError, Violation, class_isolation, snapshots_identical
from core.model.types import Event, PolicyConfig, Scenario, Topology
from core.routing.registry import get_policy
from core.sim.simulation import run_scenario

POLICIES = ["S0", "S0-QoS", "S1", "S2"]
CLASS_MIX = {0: 0.2, 1: 0.3, 2: 0.5}


@dataclass(frozen=True)
class Case:
    seed: int
    buildings: int
    n_flows: int
    load_factor: float
    events: tuple[Event, ...]

    def scenario(self) -> Scenario:
        return Scenario(
            id="property", seed=self.seed, events=list(self.events), config=PolicyConfig(),
            topology={"generator": "campus", "buildings": self.buildings, "redundancy": 0.5, "seed": self.seed},
            traffic={"generator": "campus", "n_flows": self.n_flows, "load_factor": self.load_factor,
                     "class_mix": CLASS_MIX, "seed": self.seed},
        )


def with_link_state(topology: Topology, link_state: dict[str, str]) -> Topology:
    return topology.model_copy(update={"links": [l.model_copy(update={"status": link_state[l.id]})
                                                 for l in topology.links]})


def check_case(case: Case) -> None:
    """Every invariant for every policy on one case; a failure names the case for replay."""
    try:
        scenario = case.scenario()
        resolved, flows = resolve_inputs(scenario.topology, scenario.traffic)
        for policy in POLICIES:
            snapshots = run_scenario(scenario, policy, check=True)
            assert snapshots_identical(snapshots, run_scenario(scenario, policy)), f"I8 {policy}: runs differ"
        for snap in snapshots:  # the S2 run, the last in POLICIES
            found = class_isolation(get_policy("S2"), with_link_state(resolved.topology, snap.link_state),
                                    flows, scenario.config)
            if found:
                raise InvariantError(found)
    except AssertionError as err:
        raise AssertionError(f"{err}\nreplay: check_case({case!r})") from err


@st.composite
def cases(draw) -> Case:
    seed = draw(st.integers(0, 10_000))
    buildings = draw(st.integers(1, 8))
    n_flows = draw(st.integers(1, 30))
    load_factor = draw(st.sampled_from([0.25, 0.5, 1.0, 1.5]))
    probe = Case(seed, buildings, n_flows, load_factor, ())
    try:
        resolved, _ = resolve_inputs(probe.scenario().topology, probe.scenario().traffic)
    except RuntimeError:  # no seed passes the post-failure path check at this size
        reject()
    links = sorted(l.id for l in resolved.topology.links)  # draws over sorted ids
    nodes = sorted(n.id for n in resolved.topology.nodes)
    events = []
    for step in range(1, draw(st.integers(0, 4)) + 1):
        kind = draw(st.sampled_from(["fail", "recover"]))
        if draw(st.booleans()):
            events.append(Event(step=step, kind=kind, links=draw(st.lists(st.sampled_from(links), max_size=3, unique=True))))
        else:
            events.append(Event(step=step, kind=kind, node=draw(st.sampled_from(nodes))))
    return Case(seed, buildings, n_flows, load_factor, tuple(events))


# Fixed and derandomized, so CI and a laptop draw the same cases (design, Determinism).
@settings(derandomize=True, max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(cases())
def test_every_invariant_on_every_snapshot(case):
    check_case(case)


def test_a_failure_prints_the_case_for_replay(monkeypatch):
    def broken(*args, **kwargs):
        raise InvariantError([Violation("I4", "L1>2", "forced")])

    monkeypatch.setattr("core.sim.simulation.assert_invariants", broken)
    case = Case(seed=42, buildings=3, n_flows=5, load_factor=0.5,
                events=(Event(step=1, kind="fail", links=["L6"]),))
    with pytest.raises(AssertionError) as err:
        check_case(case)
    message = str(err.value)
    assert "I4 L1>2: forced" in message
    assert "replay: check_case(Case(seed=42, buildings=3, n_flows=5, load_factor=0.5, events=(Event(" in message
    assert eval(message.split("replay: check_case(", 1)[1][:-1]) == case  # the printed case rebuilds it
