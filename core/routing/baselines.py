"""S0 and S0-QoS: latency-shortest routes with no admission control (PLAN.md section 5).

Delivery is the single-pass model: loss upstream still counts as load downstream, so the
baselines under-deliver slightly. Scale factors are exact fractions and only the final
delivery is converted to float, so 7 Mbps at scale 2/5 is 2.8 on every machine.
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

Scale = Callable[[FlowSpec, Sequence[str]], Fraction]


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
    make_scale: Callable[[dict[str, ArcSpec], dict[str, int], dict[str, dict[int, int]]], Scale],
    prev,
    step: int,
    failed_links: Sequence[str],
) -> RouteResult:
    validate_flows(flows)
    arcs = sorted(arcs, key=lambda a: a.id)
    by_id = {a.id: a for a in arcs}
    routes = _routes(arcs, flows)
    load, by_class = _offered_load(flows, routes)
    scale_of = make_scale(by_id, load, by_class)

    outcomes: dict[str, FlowOutcome] = {}
    records = []
    paths: tuple[PathRate, ...]
    for f in sorted(flows, key=lambda f: f.id):
        route = routes[f.id]
        if route is None:
            delivered, cause, paths = Fraction(0), "DISCONNECTED", ()
        else:
            scale = scale_of(f, route)
            delivered = f.rate * scale
            cause = "OVERLOAD_LOSS" if scale < 1 else "NONE"
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


def route_s0(arcs, flows, cfg: AllocConfig | None = None, *, prev=None, step=0, failed_links=()) -> RouteResult:
    """S0: each flow scaled by the worst min(1, capacity / load) on its path."""

    def make_scale(by_id, load, by_class):
        def scale(flow: FlowSpec, route: Sequence[str]) -> Fraction:
            return min(
                (min(Fraction(1), Fraction(by_id[a].capacity, load[a])) for a in route if load[a] > 0),
                default=Fraction(1),
            )

        return scale

    return _route_baseline(arcs, flows, make_scale, prev, step, failed_links)


def route_s0_qos(arcs, flows, cfg: AllocConfig | None = None, *, prev=None, step=0, failed_links=()) -> RouteResult:
    """S0-QoS: the S0 routes, with each arc serving classes in strict priority order."""

    def make_scale(by_id, load, by_class):
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
