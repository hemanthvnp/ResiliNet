"""Decision record builder: facts in, record out (add-decision-explanations).

Policies pass what they know about one flow; the builder adds the reference status, the
max-flow bound, the cut and the explanation text.
"""

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field

from core.explain.bound import greedy_gap, maxflow_bound
from core.explain.cut import residual_cut
from core.explain.data import Attempt, CutArc, DecisionRecordData
from core.explain.template import explain
from core.routing.inputs import ArcSpec, FlowSpec, PathRate
from core.routing.pathfinder import Arc, shortest_path


@dataclass
class FlowFacts:
    flow: FlowSpec
    step: int
    failed_links: tuple[str, ...]
    previous: tuple[PathRate, ...]
    reference_arcs: tuple[str, ...]  # empty when no path is needed or none exists
    paths: tuple[PathRate, ...]
    attempts: tuple[Attempt, ...]
    delivered: float
    unserved: float
    cause: str
    # Allocator only. Baselines leave these unset and get no bound, cut or capacity status.
    is_allocator: bool = False
    pre_residual: Mapping[str, int] = field(default_factory=dict)  # residual when placement began
    post_residuals: tuple[Arc, ...] = ()  # residual of every available arc after placement
    down_arcs: tuple[tuple[str, str, str], ...] = ()
    class_breakdown: Callable[[list[str]], dict[int, int]] | None = None


def reference_arcs(arcs: Iterable[ArcSpec], src: str, dst: str, failed_links: Iterable[str]) -> tuple[str, ...]:
    """Latency-shortest path ignoring capacity, over available arcs plus the links that just failed.

    Including the just-failed links keeps the old shortest path visible so the record can say it
    became invalid, as in the section 10 example.
    """
    failed = set(failed_links)
    usable = [(a.id, a.u, a.v, a.latency) for a in sorted(arcs, key=lambda a: a.id) if a.up or a.link_id in failed]
    path = shortest_path(usable, src, dst)
    return path.arcs if path else ()


def reference_status(facts: FlowFacts) -> str:
    """USED, PARTIAL: <arc> saturated, INVALID: <link> down, or NONE: disconnected."""
    if facts.cause == "DISCONNECTED":
        return "NONE: disconnected"
    if not facts.reference_arcs:
        return "USED"
    for arc_id in facts.reference_arcs:
        link = arc_id.split(":", 1)[0]
        if link in facts.failed_links:
            return f"INVALID: {link} down"
    if not facts.is_allocator:
        return "USED"
    used = sum(p.rate for p in facts.paths if p.arcs == facts.reference_arcs)
    if used >= facts.flow.rate:
        return "USED"
    limit = min(facts.reference_arcs, key=lambda a: facts.pre_residual.get(a, 0))  # first on a tie
    return f"PARTIAL: {limit} saturated"


def build_record(facts: FlowFacts) -> DecisionRecordData:
    flow = facts.flow
    bound: int | None = None
    gap: float | None = None
    cut: tuple[CutArc, ...] = ()
    if facts.is_allocator and facts.unserved > 0:
        if facts.cause == "DISCONNECTED":
            bound, gap = 0, 0.0
        else:
            bound = maxflow_bound(facts.post_residuals, facts.paths, flow.src, flow.dst, flow.rate)
            gap = greedy_gap(bound, facts.delivered)
        if facts.cause == "INSUFFICIENT_CAPACITY":
            if facts.class_breakdown is None:
                raise ValueError("allocator facts need class_breakdown to build the cut")
            cut = residual_cut(facts.post_residuals, facts.down_arcs, flow.src, facts.class_breakdown)
    record = DecisionRecordData(
        flow_id=flow.id,
        cls=flow.cls,
        demand=flow.rate,
        step=facts.step,
        failed_links=tuple(facts.failed_links),
        previous=tuple(facts.previous),
        reference_path=facts.reference_arcs if facts.cause != "DISCONNECTED" else (),
        reference_status=reference_status(facts),
        attempts=tuple(facts.attempts),
        delivered=facts.delivered,
        unserved=facts.unserved,
        cause=facts.cause,
        cut=cut,
        maxflow_bound=bound,
        greedy_gap=gap,
    )
    record.explanation = explain(record)
    return record
