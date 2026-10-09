"""The simulation: one scenario, one policy, one config (PLAN.md sections 5 and 7).

Every event is applied atomically and followed by a full recompute, so the state
after an event depends only on which links are down, never on event history.
Affected flows are found after the topology change and before routing, from the
allocation in force. The route call is timed here, because policies read no clock;
`metrics.compute_ms` is the only non-deterministic field of a snapshot.
"""

from __future__ import annotations

import json
import time
from collections.abc import Sequence

import networkx as nx

from core.gen.registry import resolve_inputs
from core.metrics.compute import compute_metrics
from core.metrics.invariants import assert_invariants
from core.model.arcs import parse_arc_id
from core.model.types import Allocation, Event, PolicyConfig, RoutingPolicy, Scenario, Snapshot, Topology
from core.sim.scenario import load_scenario


class Simulation:
    def __init__(self, scenario: Scenario | dict | str, policy: str | RoutingPolicy,
                 cfg: PolicyConfig | None = None, check: bool = False):
        self.scenario = load_scenario(scenario).model_copy(deep=True)
        resolved, flows = resolve_inputs(self.scenario.topology, self.scenario.traffic)
        self.effective_seed = resolved.seed
        self.primary_uplink = resolved.primary_uplink
        self._initial = resolved.topology.model_copy(deep=True)
        self.topology = self._initial.model_copy(deep=True)
        self.flows = list(flows)
        self.policy = _policy(policy)
        self.cfg = cfg or self.scenario.config
        self.check = check
        self.healthy_latency = _shortest_latency(self._initial, self.flows)
        self.step = 0
        self.snapshot = self._route(previous=None, affected=[])

    @property
    def allocation(self) -> Allocation:
        return self.snapshot.allocation

    def apply(self, event: Event) -> Snapshot:
        """Apply one fail or recover event (links and/or a node), recompute every route
        and return the next snapshot. Unknown ids raise before anything changes."""
        links = self._event_links(event)
        status = "down" if event.kind == "fail" else "up"
        newly_down = sorted(l.id for l in self.topology.links if l.id in links and l.status == "up"
                            and status == "down")
        self.topology = self.topology.model_copy(update={"links": [
            l.model_copy(update={"status": status}) if l.id in links else l for l in self.topology.links]})
        affected = _flows_through(self.allocation, set(newly_down))
        previous = self.allocation
        self.step += 1
        self.snapshot = self._route(previous=previous, affected=affected)
        return self.snapshot

    def reset(self) -> Snapshot:
        """Restore the scenario's initial link states and route from scratch."""
        self.topology = self._initial.model_copy(deep=True)
        self.step = 0
        self.snapshot = self._route(previous=None, affected=[])
        return self.snapshot

    def _event_links(self, event: Event) -> set[str]:
        known = {l.id for l in self.topology.links}
        unknown = sorted(set(event.links) - known)
        if unknown:
            raise KeyError(f"unknown link(s): {', '.join(unknown)}")
        links = set(event.links)
        if event.node is not None:
            if event.node not in {n.id for n in self.topology.nodes}:
                raise KeyError(f"unknown node: {event.node}")
            links |= {l.id for l in self.topology.links if event.node in (l.u, l.v)}
        return links

    def _route(self, previous: Allocation | None, affected: list[str]) -> Snapshot:
        start = time.perf_counter()
        allocation, decisions = self.policy.route(self.topology, self.flows, previous, self.cfg, step=self.step)
        compute_ms = (time.perf_counter() - start) * 1000
        metrics = compute_metrics(
            self.topology, self.flows, allocation, previous=previous, affected=affected,
            healthy_latency=self.healthy_latency, decisions=decisions, compute_ms=compute_ms)
        snapshot = Snapshot(
            step=self.step,
            link_state={l.id: l.status for l in sorted(self.topology.links, key=lambda l: l.id)},
            allocation=allocation, metrics=metrics, affected_flows=affected, decisions=decisions)
        if self.check:
            assert_invariants(snapshot, topology=self.topology, flows=self.flows, policy=self.policy.name,
                              healthy_latency=self.healthy_latency, previous=previous, cfg=self.cfg)
        return snapshot


def run_scenario(scenario: Scenario | dict | str, policy: str | RoutingPolicy,
                 cfg: PolicyConfig | None = None, check: bool = False) -> list[Snapshot]:
    """Step 0 plus one snapshot per event, events in step order. The scenario is
    deep-copied, so runs under different policies cannot affect each other."""
    simulation = Simulation(scenario, policy, cfg, check)
    events = sorted(simulation.scenario.events, key=lambda e: e.step)
    return [simulation.snapshot] + [simulation.apply(e) for e in events]


def serialize(snapshots: Sequence[Snapshot]) -> str:
    """Sorted-key JSON with metrics.compute_ms masked: the form invariant I8 compares."""
    data = [s.model_dump(mode="json") for s in snapshots]
    for d in data:
        d["metrics"]["compute_ms"] = 0.0
    return json.dumps(data, sort_keys=True)


def _policy(policy: str | RoutingPolicy) -> RoutingPolicy:
    if isinstance(policy, str):
        from core.routing.registry import get_policy
        return get_policy(policy)
    return policy


def _flows_through(allocation: Allocation, links: set[str]) -> list[str]:
    return sorted(fid for fid, r in allocation.results.items()
                  if any(parse_arc_id(a)[0] in links for p in r.paths for a in p.arcs))


def _shortest_latency(topology: Topology, flows) -> dict[str, int]:
    """Healthy shortest-path latency per flow (lat0 of PLAN.md section 8), on the
    scenario's initial topology. Flows with no path are left out."""
    g = nx.Graph()
    for l in sorted(topology.links, key=lambda l: l.id):
        if l.status == "up" and (not g.has_edge(l.u, l.v) or g[l.u][l.v]["latency"] > l.latency):
            g.add_edge(l.u, l.v, latency=l.latency)
    out = {}
    for f in sorted(flows, key=lambda f: f.id):
        if f.src == f.dst:
            out[f.id] = 0
        elif f.src in g and f.dst in g and nx.has_path(g, f.src, f.dst):
            out[f.id] = nx.shortest_path_length(g, f.src, f.dst, weight="latency")
    return out
