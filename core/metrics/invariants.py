"""Invariant checker, I1 to I11 of PLAN.md section 9.

The checker shares no code with the policies: arcs come from core.model.arcs,
connectivity from a plain networkx query, and metrics from core.metrics.compute.
It returns every violation at once, sorted by invariant number and then subject,
so a failing seed can be debugged in one read. I8 and I10 compare two runs and are
helpers; I5 is a property of the ledger and is tested there.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

import networkx as nx

from core.metrics.compute import TOLERANCE, compute_metrics
from core.model.arcs import parse_arc_id
from core.model.ledger import effective_capacity
from core.model.types import Allocation, Flow, PolicyConfig, RoutingPolicy, Snapshot, Topology

CAPACITY_AWARE = ("S1", "S2")


@dataclass(frozen=True)
class Violation:
    invariant: str  # "I1" .. "I11"
    subject: str  # flow id, arc id or metric name
    message: str

    def __str__(self) -> str:
        return f"{self.invariant} {self.subject}: {self.message}"


class InvariantError(AssertionError):
    def __init__(self, violations: list[Violation]):
        self.violations = violations
        super().__init__("\n".join(str(v) for v in violations))


def check_invariants(
    snapshot: Snapshot,
    *,
    topology: Topology,
    flows: Sequence[Flow],
    policy: str,
    healthy_latency: Mapping[str, int],
    previous: Allocation | None = None,
    cfg: PolicyConfig = PolicyConfig(),
) -> list[Violation]:
    """Every per-snapshot invariant (I1, I2, I3, I4, I6, I7, I9, I11). Link states are
    taken from the snapshot; `topology` supplies capacities and endpoints."""
    topo = _with_link_state(topology, snapshot.link_state)
    links = {l.id: l for l in topo.links}
    flows = sorted(flows, key=lambda f: f.id)
    results = snapshot.allocation.results
    found: list[Violation] = []

    # I1, I2: paths
    for f in flows:
        r = results.get(f.id)
        for path in r.paths if r else []:
            found += _check_path(f, path.arcs, links)

    # I3: demand accounting
    for f in flows:
        r = results.get(f.id)
        if r is None:
            found.append(Violation("I3", f.id, "flow has no result"))
            continue
        if r.delivered > f.rate + TOLERANCE or r.delivered < -TOLERANCE:
            found.append(Violation("I3", f.id, f"delivered {r.delivered} outside [0, demand {f.rate}]"))
        if abs(r.delivered + r.unserved - f.rate) > TOLERANCE:
            found.append(Violation("I3", f.id, f"delivered {r.delivered} + unserved {r.unserved} != demand {f.rate}"))

    # I4: capacity, for capacity-aware policies only
    if policy in CAPACITY_AWARE:
        for arc, load in sorted(snapshot.allocation.arc_load.items()):
            link = links.get(parse_arc_id(arc)[0])
            if link is not None and load > effective_capacity(link.capacity, cfg.util_cap):
                found.append(Violation("I4", arc, f"load {load} above effective capacity "
                                                  f"{effective_capacity(link.capacity, cfg.util_cap)}"))

    # I6: arc load equals the sum of path rates through the arc
    carried: dict[str, int] = {}
    for f in flows:
        for path in results[f.id].paths if f.id in results else []:
            for arc in path.arcs:
                carried[arc] = carried.get(arc, 0) + path.rate
    for arc in sorted(set(carried) | set(snapshot.allocation.arc_load)):
        reported, actual = snapshot.allocation.arc_load.get(arc, 0), carried.get(arc, 0)
        if reported != actual:
            found.append(Violation("I6", arc, f"arc_load {reported} but paths carry {actual}"))

    # I7: causes
    component = _components(topo)
    for f in flows:
        r = results.get(f.id)
        if r is None:
            continue
        src, dst = component.get(f.src), component.get(f.dst)
        connected = f.src == f.dst or (src is not None and src == dst)
        if r.unserved > TOLERANCE and r.cause == "NONE":
            found.append(Violation("I7", f.id, f"{r.unserved} unserved with cause NONE"))
        if r.cause == "DISCONNECTED" and connected:
            found.append(Violation("I7", f.id, "DISCONNECTED but a path of available links exists"))
        if r.cause == "INSUFFICIENT_CAPACITY" and not connected:
            found.append(Violation("I7", f.id, "INSUFFICIENT_CAPACITY but no path of available links exists"))

    # I9: metrics recomputed from the snapshot equal the reported ones
    recomputed = compute_metrics(
        topo, flows, snapshot.allocation, previous=previous, affected=snapshot.affected_flows,
        healthy_latency=healthy_latency, decisions=snapshot.decisions, compute_ms=snapshot.metrics.compute_ms,
    )
    for name in type(snapshot.metrics).model_fields:
        if not _same(getattr(snapshot.metrics, name), getattr(recomputed, name)):
            found.append(Violation("I9", name, f"reported {getattr(snapshot.metrics, name)!r}, "
                                               f"recomputed {getattr(recomputed, name)!r}"))

    # I11: explanation consistency, for capacity-aware policies
    if policy in CAPACITY_AWARE:
        for d in sorted(snapshot.decisions, key=lambda d: d.flow_id):
            if d.cut and d.cause != "INSUFFICIENT_CAPACITY":
                found.append(Violation("I11", d.flow_id, f"cut given with cause {d.cause}"))
            if d.unserved > TOLERANCE and (d.greedy_gap is None or d.greedy_gap < -TOLERANCE):
                found.append(Violation("I11", d.flow_id, f"greedy_gap {d.greedy_gap} for an unserved flow"))

    return sorted(found, key=lambda v: (int(v.invariant[1:]), v.subject, v.message))


def assert_invariants(snapshot: Snapshot, **kwargs) -> None:
    violations = check_invariants(snapshot, **kwargs)
    if violations:
        raise InvariantError(violations)


def snapshots_identical(a: Sequence[Snapshot], b: Sequence[Snapshot]) -> bool:
    """I8: two snapshot sequences are byte-identical once metrics.compute_ms is masked."""
    return len(a) == len(b) and all(_masked(x) == _masked(y) for x, y in zip(a, b))


def class_isolation(policy: RoutingPolicy, topology: Topology, flows: Sequence[Flow],
                    cfg: PolicyConfig) -> list[Violation]:
    """I10: routing each class with every lower class removed leaves its allocation unchanged.
    The policy is passed in, so this module does not import the routing code."""
    full, _ = policy.route(topology, list(flows), None, cfg)
    found = []
    for cls in sorted({f.cls for f in flows}):
        kept = [f for f in flows if f.cls <= cls]
        alone, _ = policy.route(topology, kept, None, cfg)
        for f in sorted((f for f in kept if f.cls == cls), key=lambda f: f.id):
            if full.results[f.id] != alone.results[f.id]:
                found.append(Violation("I10", f.id, f"class {cls} allocation changes when lower classes are removed"))
    return found


def _with_link_state(topology: Topology, link_state: Mapping[str, str]) -> Topology:
    return topology.model_copy(update={"links": [
        l.model_copy(update={"status": link_state.get(l.id, l.status)}) for l in topology.links]})


def _check_path(flow: Flow, arcs: list[str], links) -> list[Violation]:
    found = []
    if not arcs:
        return [Violation("I2", flow.id, "empty path")]
    nodes = []
    for arc in arcs:
        try:
            link_id, a, b = parse_arc_id(arc)
        except ValueError:
            found.append(Violation("I2", flow.id, f"malformed arc id {arc}"))
            continue
        link = links.get(link_id)
        if link is None or {a, b} != {link.u, link.v}:
            found.append(Violation("I2", flow.id, f"arc {arc} is not an arc of the topology"))
            continue
        if link.status != "up":
            found.append(Violation("I1", flow.id, f"arc {arc} is down"))
        if nodes and nodes[-1] != a:
            found.append(Violation("I2", flow.id, f"arc {arc} does not continue from {nodes[-1]}"))
        nodes += [a, b] if not nodes else [b]
    if nodes and (nodes[0] != flow.src or nodes[-1] != flow.dst):
        found.append(Violation("I2", flow.id, f"path runs {nodes[0]} to {nodes[-1]}, flow is {flow.src} to {flow.dst}"))
    if len(set(nodes)) != len(nodes):
        found.append(Violation("I2", flow.id, "path visits a node twice"))
    return found


def _components(topo: Topology) -> dict[str, int]:
    g = nx.Graph()
    g.add_nodes_from(sorted(n.id for n in topo.nodes))
    g.add_edges_from((l.u, l.v) for l in sorted(topo.links, key=lambda l: l.id) if l.status == "up")
    return {node: i for i, members in enumerate(sorted(nx.connected_components(g), key=min)) for node in members}


def _same(a, b) -> bool:
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    if isinstance(a, float) or isinstance(b, float):
        return a is not None and b is not None and math.isclose(a, b, rel_tol=0, abs_tol=TOLERANCE)
    return a == b


def _masked(snapshot: Snapshot) -> str:
    data = snapshot.model_dump(mode="json")
    data["metrics"]["compute_ms"] = 0.0
    return json.dumps(data, sort_keys=True)
