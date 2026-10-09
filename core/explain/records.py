"""Decision record builder: facts in, record out (add-decision-explanations).

Policies pass what they know about one flow; the builder adds the reference status, the
max-flow bound, the cut and the explanation text.
"""

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field

from core.explain.bound import greedy_gap, maxflow_bound
from core.explain.cut import residual_cut
from core.explain.template import explain
from core.model.arcs import Arc as ModelArc
from core.model.arcs import parse_arc_id
from core.model.types import Attempt, Cause, CutArc, DecisionRecord, Flow, PathAlloc
from core.routing.pathfinder import Arc, shortest_path


@dataclass
class FlowFacts:
    flow: Flow
    step: int
    failed_links: tuple[str, ...]
    previous: tuple[PathAlloc, ...]
    reference_arcs: tuple[str, ...]  # empty when no path is needed or none exists
    paths: tuple[PathAlloc, ...]
    attempts: tuple[Attempt, ...]
    delivered: float
    unserved: float
    cause: Cause
    # Allocator only. Baselines leave these unset and get no bound, cut or capacity status.
    is_allocator: bool = False
    pre_residual: Mapping[str, int] = field(default_factory=dict)  # residual when placement began
    post_residuals: tuple[Arc, ...] = ()  # residual of every available arc after placement
    down_arcs: tuple[tuple[str, str, str], ...] = ()
    class_breakdown: Callable[[list[str]], dict[int, int]] | None = None


def failed_links_of(previous: Iterable[PathAlloc], link_status: Mapping[str, str]) -> tuple[str, ...]:
    """Links that are down now and were crossed by the flow's previous paths, sorted."""
    failed: set[str] = set()
    for path in previous:
        for arc_id in path.arcs:
            link = parse_arc_id(arc_id)[0]
            if link_status.get(link) == "down":
                failed.add(link)
    return tuple(sorted(failed))


def reference_arcs(
    arcs: Iterable[ModelArc], link_status: Mapping[str, str], src: str, dst: str, failed_links: Iterable[str]
) -> tuple[str, ...]:
    """Latency-shortest path ignoring capacity, over available arcs plus the flow's failed links.

    Including the links the flow's previous paths crossed keeps the old shortest path visible
    so the record can say it became invalid, as in the section 10 example.
    """
    failed = set(failed_links)
    usable = [(a.id, a.src, a.dst, a.latency) for a in arcs if link_status[a.link] == "up" or a.link in failed]
    path = shortest_path(usable, src, dst)
    return path.arcs if path else ()


def reference_status(facts: FlowFacts) -> str:
    """USED, PARTIAL: <arc> saturated, INVALID: <link> down, or NONE: disconnected."""
    if facts.cause == "DISCONNECTED":
        return "NONE: disconnected"
    if not facts.reference_arcs:
        return "USED"
    for arc_id in facts.reference_arcs:
        link = parse_arc_id(arc_id)[0]
        if link in facts.failed_links:
            return f"INVALID: {link} down"
    if not facts.is_allocator:
        return "USED"
    used = sum(p.rate for p in facts.paths if tuple(p.arcs) == facts.reference_arcs)
    if used >= facts.flow.rate:
        return "USED"
    limit = min(facts.reference_arcs, key=lambda a: facts.pre_residual.get(a, 0))  # first on a tie
    return f"PARTIAL: {limit} saturated"


def build_record(facts: FlowFacts) -> DecisionRecord:
    flow = facts.flow
    bound: int | None = None
    gap: float | None = None
    cut: list[CutArc] = []
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
    record = DecisionRecord(
        flow_id=flow.id,
        cls=flow.cls,
        demand=flow.rate,
        step=facts.step,
        failed_links=list(facts.failed_links),
        previous=list(facts.previous),
        reference_path=list(facts.reference_arcs) if facts.cause != "DISCONNECTED" else [],
        reference_status=reference_status(facts),
        attempts=list(facts.attempts),
        delivered=facts.delivered,
        unserved=facts.unserved,
        cause=facts.cause,
        cut=cut,
        maxflow_bound=bound,
        greedy_gap=gap,
        explanation="",
    )
    return record.model_copy(update={"explanation": explain(record)})
