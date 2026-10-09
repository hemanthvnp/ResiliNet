"""Shared typed contract (PLAN.md section 7).

FROZEN at H1.5. Edited by humans only, after all four members agree, and the
fixtures under fixtures/ change first (PLAN.md section 11). Agents never edit this file.

Units: capacity and rates in integer Mbps, latency in integer ms (section 2).
`delivered` and `unserved` are floats because S0 and S0-QoS deliveries are a rate
times a scale factor; compare them with a tolerance of 1e-9.
"""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, model_validator


class _Model(BaseModel):
    # Unknown keys are an error, so a typo in a fixture or request fails loudly.
    model_config = ConfigDict(extra="forbid")


LinkStatus = Literal["up", "down"]
Cause = Literal["NONE", "DISCONNECTED", "INSUFFICIENT_CAPACITY", "PATH_LIMIT", "OVERLOAD_LOSS"]


# --- Network and traffic -----------------------------------------------------

class Node(_Model):
    id: str
    type: str
    name: str


class Link(_Model):
    id: str
    u: str
    v: str
    capacity: int
    latency: int
    status: LinkStatus


class Topology(_Model):
    nodes: list[Node]
    links: list[Link]

    @model_validator(mode="after")
    def _ids_are_consistent(self) -> Topology:
        node_ids = [n.id for n in self.nodes]
        link_ids = [l.id for l in self.links]
        for kind, ids in (("node", node_ids), ("link", link_ids)):
            dupes = sorted({i for i in ids if ids.count(i) > 1})
            if dupes:
                raise ValueError(f"duplicate {kind} id: {', '.join(dupes)}")
        known = set(node_ids)
        for link in self.links:
            missing = sorted({link.u, link.v} - known)
            if missing:
                raise ValueError(f"link {link.id} refers to unknown node: {', '.join(missing)}")
        return self


class Flow(_Model):
    id: str
    src: str
    dst: str
    rate: int
    cls: int  # 0 = P0, highest priority
    service: str = ""


# --- Allocation --------------------------------------------------------------

class PathAlloc(_Model):
    arcs: list[str]  # arc ids, "<link id>:<from>><to>", e.g. "L7:B>D"
    rate: int


class FlowResult(_Model):
    flow_id: str
    paths: list[PathAlloc]
    delivered: float  # fractional under S0 and S0-QoS
    unserved: float
    cause: Cause


class Allocation(_Model):
    results: dict[str, FlowResult]
    arc_load: dict[str, int]  # offered load per arc id


class PolicyConfig(_Model):
    order: Literal["arrival", "class_size_desc", "class_size_asc"] = "class_size_desc"
    max_paths: int = 3
    congestion_lambda: int = 0
    util_cap: float = 1.0


class Event(_Model):
    step: int
    kind: Literal["fail", "recover"]
    links: list[str] = []
    node: str | None = None


# --- Decision records (PLAN.md section 10) -----------------------------------

class Attempt(_Model):
    iter: int
    arcs: list[str]
    cost: int
    latency: int
    bottleneck: int
    pushed: int


class CutArc(_Model):
    arc: str
    state: Literal["saturated", "down"]
    load_by_class: dict[int, int]  # JSON keys are strings ("0"); loaded as int


class DecisionRecord(_Model):
    # S0 and S0-QoS fill flow_id, cls, demand, step, reference_path, delivered,
    # unserved, cause and explanation; the other fields keep their empty values.
    flow_id: str
    cls: int
    demand: int
    step: int
    failed_links: list[str]
    previous: list[PathAlloc]
    reference_path: list[str]
    reference_status: str
    attempts: list[Attempt]
    delivered: float
    unserved: float
    cause: Cause
    cut: list[CutArc]  # empty unless cause is INSUFFICIENT_CAPACITY
    maxflow_bound: int | None  # set for unserved flows under S1/S2
    greedy_gap: float | None
    explanation: str  # one line, from the fixed template in section 10


# --- Metrics (PLAN.md section 8) ---------------------------------------------

class Metrics(_Model):
    dr: float
    dr_by_class: dict[int, float]
    dr_reach: float
    unserved_by_cause: dict[str, float]
    overloaded_arcs: int
    overload_excess: int
    max_util: float
    mean_util: float
    arcs_above_90: int
    link_util: dict[str, float]  # per physical link: max of its two arcs
    latency_stretch: float
    recovery_ratio: float | None
    churn_flows: int
    churn_rate: int
    p0_greedy_gap: float
    compute_ms: float  # wall clock; masked in determinism checks


# --- Scenario and snapshot ---------------------------------------------------

class TemplateTopologySpec(_Model):
    template: str  # e.g. "campus"


class GeneratedTopologySpec(_Model):
    generator: str  # e.g. "campus"
    buildings: int
    redundancy: float
    seed: int


TopologySpec = TemplateTopologySpec | GeneratedTopologySpec


class GeneratedTrafficSpec(_Model):
    generator: str
    n_flows: int
    load_factor: float
    class_mix: dict[int, float]  # class -> share of flows
    seed: int


TrafficSpec = list[Flow] | GeneratedTrafficSpec  # an explicit list is used as given


class Scenario(_Model):
    id: str
    seed: int
    topology: TopologySpec
    traffic: TrafficSpec
    events: list[Event]
    config: PolicyConfig


class Snapshot(_Model):
    step: int
    link_state: dict[str, LinkStatus]
    allocation: Allocation
    metrics: Metrics
    affected_flows: list[str]
    decisions: list[DecisionRecord]


# --- Policy interface --------------------------------------------------------

class RoutingPolicy(Protocol):
    """Must be pure and deterministic: no globals, no clocks, no unseeded randomness.

    `prev` is copied into DecisionRecord.previous for the log. It must not
    influence the allocation.
    """

    name: str

    def route(
        self,
        topo: Topology,
        flows: list[Flow],
        prev: Allocation | None,
        cfg: PolicyConfig,
    ) -> tuple[Allocation, list[DecisionRecord]]: ...
