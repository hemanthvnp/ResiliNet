"""S0 and S0-QoS: latency-shortest routes with no admission control (PLAN.md section 5).

Delivery is the single-pass model by default: loss upstream still counts as load downstream,
so the baselines under-deliver slightly. Scale factors are exact fractions and only the final
delivery is converted to float, so 7 Mbps at scale 2/5 is 2.8 on every machine.

`upstream_aware=True` switches to the iterated model of PLAN.md section 5, where traffic lost
on an upstream arc no longer loads the arcs after it. It uses floats and stops after
MAX_ROUNDS rounds or when no scale moves by more than TOLERANCE.
"""

from collections.abc import Callable, Iterable, Sequence
from fractions import Fraction

from core.explain.records import FlowFacts, build_record, reference_arcs
from core.routing.inputs import (
    AllocConfig,
    ArcSpec,
    FlowOutcome,
    FlowSpec,
    PathRate,
    RouteResult,
    available_tuples,
    validate_flows,
)
from core.routing.pathfinder import shortest_path

MAX_ROUNDS = 50
TOLERANCE = 1e-9

Scale = Callable[[FlowSpec, Sequence[str]], Fraction | float]
MakeScale = Callable[[dict[str, ArcSpec], dict[str, int], dict[str, dict[int, int]], Sequence[FlowSpec], dict], Scale]


def _routes(arcs: Sequence[ArcSpec], flows: Sequence[FlowSpec]):
    weights = available_tuples(arcs, lambda a: a.latency)
    routes = {}
    for f in sorted(flows, key=lambda f: f.id):
        path = shortest_path(weights, f.src, f.dst)
        routes[f.id] = path.arcs if path else None
    return routes


def _offered_load(flows: Sequence[FlowSpec], routes) -> tuple[dict[str, int], dict[str, dict[int, int]]]:
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
    arcs: Iterable[ArcSpec],
    flows: Sequence[FlowSpec],
    make_scale: MakeScale,
    prev,
    step: int,
    failed_links: Sequence[str],
) -> RouteResult:
    validate_flows(flows)
    arcs = sorted(arcs, key=lambda a: a.id)
    by_id = {a.id: a for a in arcs}
    routes = _routes(arcs, flows)
    load, by_class = _offered_load(flows, routes)
    scale_of = make_scale(by_id, load, by_class, flows, routes)

    outcomes: dict[str, FlowOutcome] = {}
    records = []
    paths: tuple[PathRate, ...]
    delivered: Fraction | float
    for f in sorted(flows, key=lambda f: f.id):
        route = routes[f.id]
        if route is None:
            delivered, cause, paths = Fraction(0), "DISCONNECTED", ()
        else:
            scale = scale_of(f, route)
            delivered = f.rate * scale
            lossy = scale < 1 if isinstance(scale, Fraction) else scale < 1 - TOLERANCE
            cause = "OVERLOAD_LOSS" if lossy else "NONE"
            paths = (PathRate(tuple(route), f.rate),) if route else ()
        outcome = FlowOutcome(f.id, paths, float(delivered), float(f.rate - delivered), cause)
        outcomes[f.id] = outcome
        facts = FlowFacts(
            flow=f,
            step=step,
            failed_links=tuple(failed_links),
            previous=tuple((prev or {}).get(f.id, ())),
            reference_arcs=reference_arcs(arcs, f.src, f.dst, failed_links) if route is not None else (),
            paths=paths,
            attempts=(),
            delivered=outcome.delivered,
            unserved=outcome.unserved,
            cause=cause,
        )
        records.append(build_record(facts))
    return RouteResult(outcomes, dict(sorted(load.items())), records)


def upstream_scales(
    by_id: dict[str, ArcSpec], flows: Sequence[FlowSpec], routes, qos: bool
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


def _upstream_make_scale(qos: bool):
    def make_scale(by_id, load, by_class, flows, routes):
        arc_scale, _ = upstream_scales(by_id, flows, routes, qos)

        def scale(flow: FlowSpec, route: Sequence[str]) -> float:
            result = 1.0
            for arc_id in route:
                result *= arc_scale[(arc_id, flow.cls if qos else 0)]
            return result

        return scale

    return make_scale


def route_s0(
    arcs, flows, cfg: AllocConfig | None = None, *, prev=None, step=0, failed_links=(), upstream_aware=False
) -> RouteResult:
    """S0: each flow scaled by the worst min(1, capacity / load) on its path."""
    if upstream_aware:
        return _route_baseline(arcs, flows, _upstream_make_scale(False), prev, step, failed_links)

    def make_scale(by_id, load, by_class, flows, routes):
        def scale(flow: FlowSpec, route: Sequence[str]) -> Fraction:
            return min(
                (min(Fraction(1), Fraction(by_id[a].capacity, load[a])) for a in route if load[a] > 0),
                default=Fraction(1),
            )

        return scale

    return _route_baseline(arcs, flows, make_scale, prev, step, failed_links)


def route_s0_qos(
    arcs, flows, cfg: AllocConfig | None = None, *, prev=None, step=0, failed_links=(), upstream_aware=False
) -> RouteResult:
    """S0-QoS: the S0 routes, with each arc serving classes in strict priority order."""
    if upstream_aware:
        return _route_baseline(arcs, flows, _upstream_make_scale(True), prev, step, failed_links)

    def make_scale(by_id, load, by_class, flows, routes):
        arc_scale: dict[tuple[str, int], Fraction] = {}
        for arc_id, classes in by_class.items():
            higher = 0
            for cls in sorted(classes):
                available = max(0, by_id[arc_id].capacity - higher)
                offered = classes[cls]
                arc_scale[(arc_id, cls)] = min(Fraction(1), Fraction(available, offered)) if offered else Fraction(1)
                higher += offered

        def scale(flow: FlowSpec, route: Sequence[str]) -> Fraction:
            return min((arc_scale[(a, flow.cls)] for a in route), default=Fraction(1))

        return scale

    return _route_baseline(arcs, flows, make_scale, prev, step, failed_links)
