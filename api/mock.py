"""Mock mode: the six endpoints answered from fixtures/ (change add-rest-api, task 1.4).

The fixtures hold the healthy diamond at step 0 under each policy and no later steps, so an
event here updates link state and the step number but does not reroute. The decision endpoint
answers with the section 10 sample record, since the diamond snapshots carry no records.
Live mode replaces this once core/sim lands (tasks 2.1 to 2.4).
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import HTTPException

from api.schemas import (
    CompareRequest,
    CompareResponse,
    CompareRow,
    EventRequest,
    RunRequest,
    RunResponse,
    ScenarioInfo,
)
from api.sessions import SessionStore
from core.model.types import (
    DecisionRecord,
    Flow,
    PolicyConfig,
    Scenario,
    Snapshot,
    TemplateTopologySpec,
    Topology,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

SNAPSHOT_FILES = {
    "S0": "diamond_healthy_s0.json",
    "S0-QoS": "diamond_healthy_s0qos.json",
    "S1": "diamond_healthy_s1.json",
    "S2": "diamond_healthy_s2.json",
}


def _load(model, rel: str):
    return model.model_validate_json((FIXTURES / rel).read_text(encoding="utf-8"))


class MockBackend:
    def __init__(self) -> None:
        self.topology = _load(Topology, "topologies/diamond.json")
        self.flows = [Flow.model_validate(f) for f in json.loads((FIXTURES / "flows/diamond.json").read_text())]
        self.scenario = Scenario(
            id="07_diamond",
            seed=0,
            topology=TemplateTopologySpec(template="diamond"),
            traffic=self.flows,
            events=[],
            config=PolicyConfig(),
        )
        self.step0 = {p: _load(Snapshot, f"snapshots/{f}") for p, f in SNAPSHOT_FILES.items()}
        self.sample_record = _load(DecisionRecord, "decisions/section10_f12.json")
        self.sessions = SessionStore()  # state: (policy, current snapshot)

    def _check_scenario(self, req: RunRequest | CompareRequest) -> None:
        if req.scenario is not None:
            raise HTTPException(422, "mock mode serves built-in scenarios only; use scenario_id '07_diamond'")
        if req.scenario_id != "07_diamond":
            raise HTTPException(404, f"unknown scenario {req.scenario_id!r}")
        if req.config not in (None, PolicyConfig()):
            raise HTTPException(422, "mock mode serves the default config only; fixtures are not recomputed")

    def _check_policy(self, policy: str) -> None:
        if policy not in self.step0:
            raise HTTPException(422, f"unknown policy {policy!r}; expected one of {sorted(self.step0)}")

    def scenarios(self) -> list[ScenarioInfo]:
        return [ScenarioInfo(id="07_diamond", name="Critical vs ordinary competing", description="Diamond example of PLAN.md section 4 (mock)")]

    def create_run(self, req: RunRequest) -> RunResponse:
        self._check_scenario(req)
        self._check_policy(req.policy)
        snapshot = self.step0[req.policy]
        run_id = self.sessions.create((req.policy, snapshot))
        return RunResponse(
            run_id=run_id, scenario=self.scenario, topology=self.topology, flows=self.flows, snapshot=snapshot
        )

    def apply_event(self, run_id: str, event: EventRequest) -> Snapshot:
        with self.sessions.locked(run_id) as session:  # unknown run is 404 before any 422 on the body
            link_ids = {l.id for l in self.topology.links}
            unknown = sorted(set(event.links) - link_ids)
            if unknown:
                raise HTTPException(422, f"unknown link {', '.join(unknown)}")
            targets = set(event.links)
            if event.node is not None:
                if event.node not in {n.id for n in self.topology.nodes}:
                    raise HTTPException(422, f"unknown node {event.node!r}")
                targets |= {l.id for l in self.topology.links if event.node in (l.u, l.v)}
            status = "down" if event.kind == "fail" else "up"
            policy, current = session.state
            link_state = {**current.link_state, **{l: status for l in targets}}
            nxt = current.model_copy(update={"step": current.step + 1, "link_state": link_state})
            session.state = (policy, nxt)
        return nxt

    def reset(self, run_id: str) -> Snapshot:
        with self.sessions.locked(run_id) as session:
            policy, _ = session.state
            session.state = (policy, self.step0[policy])
        return self.step0[policy]

    def compare(self, req: CompareRequest) -> CompareResponse:
        self._check_scenario(req)
        for policy in req.policies:
            self._check_policy(policy)
        return CompareResponse(
            scenario=self.scenario,
            topology=self.topology,
            flows=self.flows,
            table=[CompareRow(policy=p, metrics=self.step0[p].metrics) for p in req.policies],
            snapshots={p: [self.step0[p]] for p in req.policies},
        )

    def decision(self, run_id: str, flow_id: str) -> DecisionRecord:
        with self.sessions.locked(run_id):
            pass
        if flow_id not in {f.id for f in self.flows}:
            raise HTTPException(404, f"unknown flow {flow_id!r}")
        return self.sample_record
