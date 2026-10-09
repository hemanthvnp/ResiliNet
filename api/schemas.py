"""Request and response bodies of the six endpoints (PLAN.md section 7; change add-rest-api, design).

Everything inside a body is a frozen model from core/model/types.py; this module only adds the
envelopes. Unknown keys are rejected, as in the contract.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from core.model.types import Flow, Metrics, PolicyConfig, Scenario, Snapshot, Topology


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ScenarioInfo(_Body):
    id: str
    name: str
    description: str


class _ScenarioChoice(_Body):
    """Exactly one of a built-in scenario id or an inline scenario."""

    scenario_id: str | None = None
    scenario: Scenario | None = None

    @model_validator(mode="after")
    def _exactly_one(self):
        if (self.scenario_id is None) == (self.scenario is None):
            raise ValueError("give exactly one of scenario_id or scenario")
        return self


class RunRequest(_ScenarioChoice):
    policy: str
    config: PolicyConfig | None = None


class RunResponse(_Body):
    run_id: str
    scenario: Scenario
    topology: Topology
    flows: list[Flow]
    snapshot: Snapshot


class EventRequest(_Body):
    """The server assigns the step, so a stale client cannot send one."""

    kind: Literal["fail", "recover"]
    links: list[str] = []
    node: str | None = None


class CompareRequest(_ScenarioChoice):
    policies: list[str]
    config: PolicyConfig | None = None


class CompareRow(_Body):
    policy: str
    metrics: Metrics  # of the final step


class CompareResponse(_Body):
    """Self-contained, so a saved `compare --out` file renders with no server."""

    scenario: Scenario
    topology: Topology
    flows: list[Flow]
    table: list[CompareRow]  # in the order of the request's policies
    snapshots: dict[str, list[Snapshot]]  # per policy, one per step
