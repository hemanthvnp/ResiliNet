"""The S1/S2 allocator: flows placed in order on the residual graph (PLAN.md section 5).

Every call starts from an empty ledger. `prev` is copied into the decision record and never
read by the placement loop.
"""

from collections.abc import Sequence

from core.explain.records import FlowFacts, build_record, failed_links_of, reference_arcs
from core.model.arcs import all_arcs, available_arcs
from core.model.ledger import Ledger
from core.model.types import (
    Allocation,
    Attempt,
    Cause,
    DecisionRecord,
    Flow,
    FlowResult,
    PathAlloc,
    PolicyConfig,
    Topology,
)
from core.routing.checks import validate_inputs
from core.routing.cost import arc_cost
from core.routing.ordering import order_flows
from core.routing.pathfinder import connected_components, residual_reachable, shortest_path


def allocate(
    topo: Topology,
    flows: Sequence[Flow],
    prev: Allocation | None,
    cfg: PolicyConfig,
    *,
    step: int = 0,
) -> tuple[Allocation, list[DecisionRecord]]:
    validate_inputs(flows, cfg)
    available = available_arcs(topo)
    by_id = {a.id: a for a in available}
    down_arcs = tuple((a.id, a.src, a.dst) for a in all_arcs(topo) if a.id not in by_id)
    link_status = {link.id: link.status for link in topo.links}
    every_arc = all_arcs(topo)
    ledger = Ledger(topo, cfg.util_cap)

    nodes = {n.id for n in topo.nodes} | {f.src for f in flows} | {f.dst for f in flows}
    component = {
        node: index
        for index, members in enumerate(connected_components(nodes, [(a.id, a.src, a.dst, 0) for a in available]))
        for node in members
    }

    def residual_arcs() -> list[tuple[str, str, str, int]]:
        return [(a.id, a.src, a.dst, ledger.residual(a.id)) for a in available]

    results: dict[str, FlowResult] = {}
    records: list[DecisionRecord] = []
    for f in order_flows(flows, cfg.order):
        paths: list[PathAlloc] = []
        attempts: list[Attempt] = []
        remaining = f.rate
        cause: Cause = "NONE"
        pre_residual = {a.id: ledger.residual(a.id) for a in available}

        if f.rate == 0 or f.src == f.dst:
            remaining = 0  # served in full without touching the network
        elif component[f.src] != component[f.dst]:
            cause = "DISCONNECTED"
        else:
            while remaining > 0 and len(paths) < cfg.max_paths:
                weighted = [
                    (a.id, a.src, a.dst, arc_cost(a.latency, ledger.load(a.id), a.capacity, cfg.congestion_lambda))
                    for a in available
                    if ledger.residual(a.id) > 0
                ]
                path = shortest_path(weighted, f.src, f.dst)
                if path is None:
                    break
                arcs = list(path.arcs)
                bottleneck = ledger.bottleneck(arcs)
                pushed = min(remaining, bottleneck)
                ledger.reserve(arcs, pushed, f.cls)
                paths.append(PathAlloc(arcs=arcs, rate=pushed))
                latency = sum(by_id[a].latency for a in arcs)
                attempts.append(
                    Attempt(
                        iter=len(attempts) + 1,
                        arcs=arcs,
                        cost=path.cost,
                        latency=latency,
                        bottleneck=bottleneck,
                        pushed=pushed,
                    )
                )
                remaining -= pushed
            if remaining > 0:
                reachable = residual_reachable(residual_arcs(), f.src)
                cause = "PATH_LIMIT" if f.dst in reachable else "INSUFFICIENT_CAPACITY"

        result = FlowResult(
            flow_id=f.id, paths=paths, delivered=float(f.rate - remaining), unserved=float(remaining), cause=cause
        )
        results[f.id] = result
        previous = tuple(prev.results[f.id].paths) if prev and f.id in prev.results else ()
        failed = failed_links_of(previous, link_status)
        facts = FlowFacts(
            flow=f,
            step=step,
            failed_links=failed,
            previous=previous,
            reference_arcs=reference_arcs(every_arc, link_status, f.src, f.dst, failed) if f.src != f.dst else (),
            paths=tuple(paths),
            attempts=tuple(attempts),
            delivered=result.delivered,
            unserved=result.unserved,
            cause=cause,
            is_allocator=True,
            pre_residual=pre_residual,
            post_residuals=tuple(residual_arcs()) if remaining > 0 else (),
            down_arcs=down_arcs,
            class_breakdown=ledger.class_breakdown,
        )
        records.append(build_record(facts))

    arc_load = {arc_id: ledger.load(arc_id) for arc_id in ledger.arcs}  # every available arc, as in fixtures/
    return Allocation(results=results, arc_load=arc_load), records
