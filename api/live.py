"""Live mode: the six endpoints on core/sim (change add-rest-api, tasks 2.2 to 3.4).

No routing, metric or simulation logic lives here; every number comes from core.Simulation.
A session's state is its Simulation, used only under the session's lock.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fastapi import HTTPException

from api.schemas import CompareRequest, CompareResponse, CompareRow, EventRequest, RunRequest, RunResponse, ScenarioInfo
from api.sessions import SessionStore
from core.gen.registry import resolve_inputs
from core.model.types import DecisionRecord, Event, GeneratedTopologySpec, PolicyConfig, Scenario, Snapshot
from core.sim.scenario import load_fixture
from core.sim.simulation import Simulation

SCENARIO_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "scenarios"

# id -> (name, description), from the scenario table of PLAN.md section 9
SCENARIO_INFO = {
    "01_normal": ("Normal operation", "Campus template, load factor about 0.5"),
    "02_uplink_failure": ("Single critical-link failure", "Fail the primary uplink"),
    "03_three_links": ("Multiple simultaneous failures", "Fail 3 links in one event"),
    "04_congestion": ("Congestion on alternatives", "Two alternate routes, one nearly full"),
    "05_insufficient_capacity": ("Insufficient capacity", "Demand exceeds the min-cut"),
    "06_disconnected": ("Disconnected destination", "Isolate a hostel"),
    "07_diamond": ("Critical vs ordinary competing", "Diamond example of PLAN.md section 4"),
    "08_recovery": ("Link recovery", "Fail then recover"),
}


@contextmanager
def core_errors() -> Iterator[None]:
    """The one place core exceptions become HTTP errors (task 2.5). Core raises ValueError for
    bad input (unknown policy, bad spec), KeyError for an unknown link, node, template or
    generator, and RuntimeError when the generator exhausts its retries: all are the caller's
    input, so 422 naming the value. Anything else is a bug and stays a 500."""
    # ponytail: a KeyError or ValueError from a bug inside routing would also read as 422; split
    # validation from routing in core if that ever hides a real defect.
    try:
        yield
    except (ValueError, KeyError, RuntimeError) as err:
        raise HTTPException(422, str(err.args[0]) if err.args else type(err).__name__) from err


class LiveBackend:
    def __init__(self, check: bool = False) -> None:
        self.check = check  # run the invariant checker on every snapshot (tests)
        fixtures = [load_fixture(p).scenario for p in SCENARIO_DIR.glob("*.json")]
        self.builtin = {s.id: s for s in sorted(fixtures, key=lambda s: s.id)}
        self.sessions = SessionStore()  # state: Simulation

    def _scenario(self, req: RunRequest | CompareRequest) -> Scenario:
        if req.scenario is not None:
            return req.scenario
        if req.scenario_id not in self.builtin:
            raise HTTPException(404, f"unknown scenario {req.scenario_id!r}")
        return self.builtin[req.scenario_id]

    @staticmethod
    def _effective(scenario: Scenario, cfg: PolicyConfig | None, seed: int | None) -> Scenario:
        """The scenario as run: the config used, and the generator seed after any retry."""
        update = {"config": cfg or scenario.config}
        if isinstance(scenario.topology, GeneratedTopologySpec):
            update["topology"] = scenario.topology.model_copy(update={"seed": seed})
        return scenario.model_copy(update=update)

    def scenarios(self) -> list[ScenarioInfo]:
        return [ScenarioInfo(id=sid, name=SCENARIO_INFO.get(sid, (sid, ""))[0],
                             description=SCENARIO_INFO.get(sid, ("", ""))[1]) for sid in self.builtin]

    def create_run(self, req: RunRequest) -> RunResponse:
        scenario = self._scenario(req)
        with core_errors():
            sim = Simulation(scenario, req.policy, req.config, check=self.check)
        run_id = self.sessions.create(sim)
        return RunResponse(run_id=run_id, scenario=self._effective(scenario, req.config, sim.effective_seed),
                           topology=sim.topology, flows=sim.flows, snapshot=sim.snapshot)

    def apply_event(self, run_id: str, event: EventRequest) -> Snapshot:
        with self.sessions.locked(run_id) as session, core_errors():
            sim: Simulation = session.state
            # Simulation checks every id before changing anything, so a 422 leaves the run as it was.
            return sim.apply(Event(step=sim.step + 1, kind=event.kind, links=event.links, node=event.node))

    def reset(self, run_id: str) -> Snapshot:
        with self.sessions.locked(run_id) as session:
            return session.state.reset()

    def compare(self, req: CompareRequest) -> CompareResponse:
        """Each policy runs the scenario's full event list on its own Simulation, which
        deep-copies the scenario, so every policy sees the same links, flows and events."""
        scenario = self._scenario(req)
        events = sorted(scenario.events, key=lambda e: e.step)
        snapshots: dict[str, list[Snapshot]] = {}
        with core_errors():
            for policy in req.policies:
                sim = Simulation(scenario, policy, req.config, check=self.check)
                snapshots[policy] = [sim.snapshot] + [sim.apply(e) for e in events]
            resolved, flows = resolve_inputs(scenario.topology, scenario.traffic)
        return CompareResponse(
            scenario=self._effective(scenario, req.config, resolved.seed), topology=resolved.topology, flows=flows,
            table=[CompareRow(policy=p, metrics=snapshots[p][-1].metrics) for p in req.policies],
            snapshots=snapshots,
        )

    def decision(self, run_id: str, flow_id: str) -> DecisionRecord:
        with self.sessions.locked(run_id) as session:
            sim: Simulation = session.state
            if flow_id not in {f.id for f in sim.flows}:
                raise HTTPException(404, f"unknown flow {flow_id!r}")
            records = {d.flow_id: d for d in sim.snapshot.decisions}
        if flow_id not in records:
            raise HTTPException(404, f"no decision record for flow {flow_id!r} under {sim.policy.name}")
        return records[flow_id]
