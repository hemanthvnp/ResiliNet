"""S0 and S0-QoS: latency-shortest routes with no admission control (PLAN.md section 5).

Delivery is the single-pass model by default: loss upstream still counts as load downstream,
so the baselines under-deliver slightly. Scale factors are exact fractions and only the final
delivery is converted to float, so 7 Mbps at scale 2/5 is 2.8 on every machine.

`upstream_aware=True` switches to the iterated model of PLAN.md section 5, where traffic lost
on an upstream arc no longer loads the arcs after it. It uses floats and stops after
MAX_ROUNDS rounds or when no scale moves by more than TOLERANCE.
"""

from collections.abc import Callable, Sequence
from fractions import Fraction

from core.explain.records import FlowFacts, build_record, failed_links_of, reference_arcs
from core.model.arcs import Arc, all_arcs, available_arcs
from core.model.types import Allocation, Cause, DecisionRecord, Flow, FlowResult, PathAlloc, PolicyConfig, Topology
from core.routing.checks import validate_inputs
from core.routing.pathfinder import shortest_path

MAX_ROUNDS = 50
TOLERANCE = 1e-9

Scale = Callable[[Flow, Sequence[str]], Fraction | float]
MakeScale = Callable[[dict[str, Arc], dict[str, int], dict[str, dict[int, int]], Sequence[Flow], dict], Scale]


def _routes(arcs: Sequence[Arc], flows: Sequence[Flow]) -> dict[str, tuple[str, ...] | None]:
    weights = [(a.id, a.src, a.dst, a.latency) for a in arcs]
    routes: dict[str, tuple[str, ...] | None] = {}
    for f in sorted(flows, key=lambda f: f.id):
        path = shortest_path(weights, f.src, f.dst)
        routes[f.id] = path.arcs if path else None
    return routes


def _offered_load(flows: Sequence[Flow], routes) -> tuple[dict[str, int], dict[str, dict[int, int]]]:
    """Offered load per arc, and per arc and class."""
    load: dict[str, int] = {}
    by_class: dict[str, dict[int, int]] = {}
    for f in sorted(flows, key=lambda f: f.id):
        for arc_id in routes[f.id] or ():
            load[arc_id] = load.get(arc_id, 0) + f.rate
            by_class.setdefault(arc_id, {})
            by_class[arc_id][f.cls] = by_class[arc_id].get(f.cls, 0) + f.rate
    return load, by_class


def _route_baseline(
    topo: Topology,
    flows: Sequence[Flow],
    make_scale: MakeScale,
    prev: Allocation | None,
    step: int,
) -> tuple[Allocation, list[DecisionRecord]]:
    available = available_arcs(topo)
    every_arc = all_arcs(topo)
    by_id = {a.id: a for a in available}
    link_status = {link.id: link.status for link in topo.links}
    routes = _routes(available, flows)
    load, by_class = _offered_load(flows, routes)
    scale_of = make_scale(by_id, load, by_class, flows, routes)

    results: dict[str, FlowResult] = {}
    records: list[DecisionRecord] = []
    for f in sorted(flows, key=lambda f: f.id):
        route = routes[f.id]
        delivered: Fraction | float
        cause: Cause
        paths: list[PathAlloc] = []
        if route is None:
            delivered, cause = Fraction(0), "DISCONNECTED"
        else:
            scale = scale_of(f, route)
            delivered = f.rate * scale
            lossy = scale < 1 if isinstance(scale, Fraction) else scale < 1 - TOLERANCE
            cause = "OVERLOAD_LOSS" if lossy else "NONE"
            if route:
                paths = [PathAlloc(arcs=list(route), rate=f.rate)]
        result = FlowResult(
            flow_id=f.id, paths=paths, delivered=float(delivered), unserved=float(f.rate - delivered), cause=cause
        )
        results[f.id] = result
        previous = tuple(prev.results[f.id].paths) if prev and f.id in prev.results else ()
        failed = failed_links_of(previous, link_status)
        facts = FlowFacts(
            flow=f,
            step=step,
            failed_links=failed,
            previous=previous,
            reference_arcs=reference_arcs(every_arc, link_status, f.src, f.dst, failed) if route is not None else (),
            paths=tuple(paths),
            attempts=(),
            delivered=result.delivered,
            unserved=result.unserved,
            cause=cause,
        )
        records.append(build_record(facts))
    arc_load = {a.id: load.get(a.id, 0) for a in available}  # every available arc, as in fixtures/
    return Allocation(results=results, arc_load=arc_load), records


def upstream_scales(
    by_id: dict[str, Arc], flows: Sequence[Flow], routes, qos: bool
) -> tuple[dict[tuple[str, int], float], bool]:
    """Scale factor per (arc, class) once upstream loss is taken into account, and whether the
    iteration converged. Without `qos` all flows share one class key, so an arc scales everyone
    by min(1, capacity / arriving load). With `qos` it serves classes in priority order.
    """
    ordered = sorted(flows, key=lambda f: f.id)
    key = (lambda f: f.cls) if qos else (lambda f: 0)
    scale = {(a, key(f)): 1.0 for f in ordered for a in routes[f.id] or ()}
    for _ in range(MAX_ROUNDS):
        arriving: dict[str, dict[int, float]] = {}
        for f in ordered:
            rate = float(f.rate)
            for arc_id in routes[f.id] or ():
                by_class = arriving.setdefault(arc_id, {})
                by_class[key(f)] = by_class.get(key(f), 0.0) + rate
                rate *= scale[(arc_id, key(f))]
        updated = {}
        for arc_id in sorted(arriving):
            higher = 0.0
            for cls in sorted(arriving[arc_id]):
                offered = arriving[arc_id][cls]
                available = max(0.0, by_id[arc_id].capacity - higher)
                updated[(arc_id, cls)] = min(1.0, available / offered) if offered else 1.0
                higher += offered
        moved = max((abs(updated[k] - scale[k]) for k in scale), default=0.0)
        scale = updated
        if moved <= TOLERANCE:
            return scale, True
    return scale, False


def _upstream_make_scale(qos: bool) -> MakeScale:
    def make_scale(by_id, load, by_class, flows, routes):
        arc_scale, _ = upstream_scales(by_id, flows, routes, qos)

        def scale(flow: Flow, route: Sequence[str]) -> float:
            result = 1.0
            for arc_id in route:
                result *= arc_scale[(arc_id, flow.cls if qos else 0)]
            return result

        return scale

    return make_scale


def route_s0(
    topo: Topology,
    flows: Sequence[Flow],
    prev: Allocation | None = None,
    cfg: PolicyConfig | None = None,
    *,
    step: int = 0,
    upstream_aware: bool = False,
) -> tuple[Allocation, list[DecisionRecord]]:
    """S0: each flow scaled by the worst min(1, capacity / load) on its path."""
    validate_inputs(flows, cfg or PolicyConfig())
    if upstream_aware:
        return _route_baseline(topo, flows, _upstream_make_scale(False), prev, step)

    def make_scale(by_id, load, by_class, flows, routes):
        def scale(flow: Flow, route: Sequence[str]) -> Fraction:
            return min(
                (min(Fraction(1), Fraction(by_id[a].capacity, load[a])) for a in route if load[a] > 0),
                default=Fraction(1),
            )

        return scale

    return _route_baseline(topo, flows, make_scale, prev, step)


def route_s0_qos(
    topo: Topology,
    flows: Sequence[Flow],
    prev: Allocation | None = None,
    cfg: PolicyConfig | None = None,
    *,
    step: int = 0,
    upstream_aware: bool = False,
) -> tuple[Allocation, list[DecisionRecord]]:
    """S0-QoS: the S0 routes, with each arc serving classes in strict priority order."""
    validate_inputs(flows, cfg or PolicyConfig())
    if upstream_aware:
        return _route_baseline(topo, flows, _upstream_make_scale(True), prev, step)

    def make_scale(by_id, load, by_class, flows, routes):
        arc_scale: dict[tuple[str, int], Fraction] = {}
        for arc_id, classes in by_class.items():
            higher = 0
            for cls in sorted(classes):
                available = max(0, by_id[arc_id].capacity - higher)
                offered = classes[cls]
                arc_scale[(arc_id, cls)] = min(Fraction(1), Fraction(available, offered)) if offered else Fraction(1)
                higher += offered

        def scale(flow: Flow, route: Sequence[str]) -> Fraction:
            return min((arc_scale[(a, flow.cls)] for a in route), default=Fraction(1))

        return scale

    return _route_baseline(topo, flows, make_scale, prev, step)
