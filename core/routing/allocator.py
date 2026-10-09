"""The S1/S2 allocator: flows placed in order on the residual graph (PLAN.md section 5).

Every call starts from an empty ledger. `prev` is copied into the decision record and never
read by the placement loop.
"""

from collections.abc import Callable, Iterable, Mapping, Sequence

from core.explain.data import Attempt
from core.explain.records import FlowFacts, build_record, reference_arcs
from core.routing.cost import arc_cost
from core.routing.inputs import (
    AllocConfig,
    ArcSpec,
    FlowOutcome,
    FlowSpec,
    PathRate,
    RouteResult,
    validate_flows,
)
from core.routing.ledger_standin import SimpleLedger
from core.routing.ordering import order_flows
from core.routing.pathfinder import connected_components, residual_reachable, shortest_path

LedgerFactory = Callable[[Sequence[ArcSpec], float], SimpleLedger]


def allocate(
    arcs: Iterable[ArcSpec],
    flows: Sequence[FlowSpec],
    cfg: AllocConfig,
    *,
    prev: Mapping[str, Sequence[PathRate]] | None = None,
    step: int = 0,
    failed_links: Sequence[str] = (),
    ledger_factory: LedgerFactory = SimpleLedger,
) -> RouteResult:
    validate_flows(flows)
    arcs = sorted(arcs, key=lambda a: a.id)
    available = [a for a in arcs if a.up]
    by_id = {a.id: a for a in arcs}
    down_arcs = tuple((a.id, a.u, a.v) for a in arcs if not a.up)
    ledger = ledger_factory(arcs, cfg.util_cap)

    nodes = {a.u for a in arcs} | {a.v for a in arcs} | {f.src for f in flows} | {f.dst for f in flows}
    component = {
        node: index
        for index, members in enumerate(connected_components(nodes, [(a.id, a.u, a.v, 0) for a in available]))
        for node in members
    }

    def load(arc_id: str) -> int:
        return sum(ledger.class_breakdown([arc_id]).values())

    def residual_arcs() -> list[tuple[str, str, str, int]]:
        return [(a.id, a.u, a.v, ledger.residual(a.id)) for a in available]

    outcomes: dict[str, FlowOutcome] = {}
    records = []
    for f in order_flows(flows, cfg.order):
        paths: list[PathRate] = []
        attempts: list[Attempt] = []
        remaining = f.rate
        cause = "NONE"
        pre_residual = {a.id: ledger.residual(a.id) for a in available}

        if f.rate == 0 or f.src == f.dst:
            remaining = 0  # served in full without touching the network
        elif component[f.src] != component[f.dst]:
            cause = "DISCONNECTED"
        else:
            while remaining > 0 and len(paths) < cfg.max_paths:
                weighted = [
                    (a.id, a.u, a.v, arc_cost(a.latency, load(a.id), a.capacity, cfg.congestion_lambda))
                    for a in available
                    if ledger.residual(a.id) > 0
                ]
                path = shortest_path(weighted, f.src, f.dst)
                if path is None:
                    break
                bottleneck = ledger.bottleneck(path.arcs)
                pushed = min(remaining, bottleneck)
                ledger.reserve(path.arcs, pushed, f.cls)
                paths.append(PathRate(path.arcs, pushed))
                latency = sum(by_id[a].latency for a in path.arcs)
                attempts.append(Attempt(len(attempts) + 1, path.arcs, path.cost, latency, bottleneck, pushed))
                remaining -= pushed
            if remaining > 0:
                reachable = residual_reachable(residual_arcs(), f.src)
                cause = "PATH_LIMIT" if f.dst in reachable else "INSUFFICIENT_CAPACITY"

        outcome = FlowOutcome(f.id, tuple(paths), float(f.rate - remaining), float(remaining), cause)
        outcomes[f.id] = outcome
        facts = FlowFacts(
            flow=f,
            step=step,
            failed_links=tuple(failed_links),
            previous=tuple((prev or {}).get(f.id, ())),
            reference_arcs=reference_arcs(arcs, f.src, f.dst, failed_links) if f.src != f.dst else (),
            paths=tuple(paths),
            attempts=tuple(attempts),
            delivered=outcome.delivered,
            unserved=outcome.unserved,
            cause=cause,
            is_allocator=True,
            pre_residual=pre_residual,
            post_residuals=tuple(residual_arcs()) if remaining > 0 else (),
            down_arcs=down_arcs,
            class_breakdown=ledger.class_breakdown,
        )
        records.append(build_record(facts))

    arc_load = {a.id: load(a.id) for a in available if load(a.id) > 0}
    return RouteResult(outcomes, arc_load, records)
