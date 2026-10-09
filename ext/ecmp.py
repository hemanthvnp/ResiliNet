"""ECMP-style baselines (change ecmp-baseline; PLAN-CYCLE2.md section 3.1).

An idealised fluid split, not a router's ECMP: real routers hash whole flows to next hops.

Routing, the same for both policies:
- The equal-cost next hops of node u, for a flow to d, are its available arcs (u, v) with
  latency(u, v) + dist(v) == dist(u), where dist is the latency-shortest distance to d.
  They are ordered by (neighbour id, link id), and at most MAX_NEXT_HOPS are used.
- From the source, each node splits the integer amount it receives: amount // n per next hop,
  with the remainder given 1 Mbps at a time to the first next hops. A branch that receives
  0 is dropped, so path rates are integers that sum to the flow's rate.

Delivery repeats the cycle-1 single-pass formulas per path (core/routing/baselines.py keeps
them private to single-route flows):
- ECMP: a path delivers rate x min over its arcs of min(1, capacity / load).
- ECMP-QoS: each arc serves classes in priority order; a path delivers rate x the minimum,
  over its arcs, of its class's min(1, available / load of that class).
"""

from __future__ import annotations

import heapq
from collections.abc import Callable, Sequence
from fractions import Fraction

from core.explain.records import FlowFacts, build_record, failed_links_of, reference_arcs
from core.model.arcs import Arc, all_arcs, available_arcs
from core.model.types import Allocation, Cause, DecisionRecord, Flow, FlowResult, PathAlloc, PolicyConfig, Topology
from core.routing.checks import validate_inputs

MAX_NEXT_HOPS = 8  # per node; a fixed width, not a hardware claim (design.md)

Result = tuple[Allocation, list[DecisionRecord]]
Scale = Callable[[Flow, Sequence[str]], Fraction]


def distances_to(arcs: Sequence[Arc], dst: str) -> dict[str, int]:
    """Latency-shortest distance from every node that can reach `dst`, over `arcs`."""
    into: dict[str, list[Arc]] = {}
    for a in arcs:
        into.setdefault(a.dst, []).append(a)
    dist = {dst: 0}
    heap = [(0, dst)]
    while heap:
        d, node = heapq.heappop(heap)
        if d > dist[node]:
            continue
        for a in into.get(node, ()):
            if d + a.latency < dist.get(a.src, d + a.latency + 1):
                dist[a.src] = d + a.latency
                heapq.heappush(heap, (dist[a.src], a.src))
    return dist


def ecmp_paths(arcs: Sequence[Arc], flow: Flow) -> list[PathAlloc] | None:
    """The flow's paths with their integer rates, or None if its destination is unreachable."""
    dist = distances_to(arcs, flow.dst)
    if flow.src not in dist:
        return None
    out: dict[str, list[Arc]] = {}
    for a in arcs:
        out.setdefault(a.src, []).append(a)
    paths: list[PathAlloc] = []

    def walk(node: str, amount: int, route: list[str], seen: set[str]) -> None:
        if node == flow.dst:
            if route:
                paths.append(PathAlloc(arcs=list(route), rate=amount))
            return
        hops = sorted((a for a in out.get(node, ()) if a.dst in dist and a.dst not in seen
                       and a.latency + dist[a.dst] == dist[node]),
                      key=lambda a: (a.dst, a.link))[:MAX_NEXT_HOPS]
        if not hops:  # ponytail: only reachable through zero-latency loops; that amount is lost
            return
        share, extra = divmod(amount, len(hops))
        for i, a in enumerate(hops):
            branch = share + (1 if i < extra else 0)
            if branch:
                walk(a.dst, branch, route + [a.id], seen | {a.dst})

    walk(flow.src, flow.rate, [], {flow.src})
    return paths


def proportional(by_id: dict[str, Arc], load: dict[str, int], by_class: dict[str, dict[int, int]]) -> Scale:
    def scale(flow: Flow, route: Sequence[str]) -> Fraction:
        return min((min(Fraction(1), Fraction(by_id[a].capacity, load[a])) for a in route), default=Fraction(1))

    return scale


def strict_priority(by_id: dict[str, Arc], load: dict[str, int], by_class: dict[str, dict[int, int]]) -> Scale:
    arc_scale: dict[tuple[str, int], Fraction] = {}
    for arc_id, classes in by_class.items():
        higher = 0
        for cls in sorted(classes):
            available = max(0, by_id[arc_id].capacity - higher)
            arc_scale[(arc_id, cls)] = min(Fraction(1), Fraction(available, classes[cls])) if classes[cls] else Fraction(1)
            higher += classes[cls]

    def scale(flow: Flow, route: Sequence[str]) -> Fraction:
        return min((arc_scale[(a, flow.cls)] for a in route), default=Fraction(1))

    return scale


def route_ecmp(topo: Topology, flows: Sequence[Flow], prev: Allocation | None, cfg: PolicyConfig | None,
               make_scale: Callable[..., Scale], step: int = 0) -> Result:
    validate_inputs(flows, cfg or PolicyConfig())
    available = available_arcs(topo)
    by_id = {a.id: a for a in available}
    link_status = {link.id: link.status for link in topo.links}
    ordered = sorted(flows, key=lambda f: f.id)
    routes = {f.id: (ecmp_paths(available, f) if f.src != f.dst else []) for f in ordered}

    load: dict[str, int] = {}
    by_class: dict[str, dict[int, int]] = {}
    for f in ordered:
        for path in routes[f.id] or ():
            for a in path.arcs:
                load[a] = load.get(a, 0) + path.rate
                by_class.setdefault(a, {})
                by_class[a][f.cls] = by_class[a].get(f.cls, 0) + path.rate
    scale = make_scale(by_id, load, by_class)

    results: dict[str, FlowResult] = {}
    records: list[DecisionRecord] = []
    for f in ordered:
        paths = routes[f.id]
        cause: Cause
        if paths is None:
            delivered, cause, paths = Fraction(0), "DISCONNECTED", []
        elif f.src == f.dst:
            delivered, cause = Fraction(f.rate), "NONE"  # delivered with no network use (PLAN.md section 13)
        else:
            delivered = sum((p.rate * scale(f, p.arcs) for p in paths), Fraction(0))
            cause = "OVERLOAD_LOSS" if delivered < f.rate else "NONE"
        result = FlowResult(flow_id=f.id, paths=paths, delivered=float(delivered),
                            unserved=float(f.rate - delivered), cause=cause)
        results[f.id] = result
        previous = tuple(prev.results[f.id].paths) if prev and f.id in prev.results else ()
        failed = failed_links_of(previous, link_status)
        records.append(build_record(FlowFacts(
            flow=f, step=step, failed_links=failed, previous=previous,
            reference_arcs=reference_arcs(all_arcs(topo), link_status, f.src, f.dst, failed) if paths else (),
            paths=tuple(paths), attempts=(), delivered=result.delivered, unserved=result.unserved, cause=cause,
        )))
    arc_load = {a.id: load.get(a.id, 0) for a in available}  # every available arc, as in fixtures/
    return Allocation(results=results, arc_load=arc_load), records


class Ecmp:
    """ECMP-style equal split per next hop, proportional loss as in S0."""

    name = "ECMP"

    def route(self, topo: Topology, flows: Sequence[Flow], prev: Allocation | None, cfg: PolicyConfig,
              *, step: int = 0) -> Result:
        return route_ecmp(topo, flows, prev, cfg, proportional, step)


class EcmpQoS:
    """The ECMP routes with strict priority on each arc, as in S0-QoS."""

    name = "ECMP-QoS"

    def route(self, topo: Topology, flows: Sequence[Flow], prev: Allocation | None, cfg: PolicyConfig,
              *, step: int = 0) -> Result:
        return route_ecmp(topo, flows, prev, cfg, strict_priority, step)
