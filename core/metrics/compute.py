"""Metrics of PLAN.md section 8 as one pure function of the simulated state.

Everything is computed from the topology, flows and allocation (plus the previous
allocation and affected flows for the change measures), never from algorithm
internals, so a snapshot's metrics can be recomputed and compared (invariant I9).
Sums run over flows in id order and arcs in arc-id order and are accumulated as
exact fractions, so the floats reported are identical between runs (invariant I8).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from fractions import Fraction

from core.model.arcs import all_arcs
from core.model.types import Allocation, DecisionRecord, Flow, Metrics, Topology

TOLERANCE = 1e-9
ABOVE = Fraction(9, 10)  # arcs_above_90 counts utilization strictly above 0.9


def _ratio(num: Fraction, den: Fraction) -> float:
    """num / den, or 1.0 when there is nothing to deliver (design: zero demand)."""
    return float(num / den) if den else 1.0


def compute_metrics(
    topology: Topology,
    flows: Sequence[Flow],
    allocation: Allocation,
    *,
    previous: Allocation | None = None,
    affected: Iterable[str] = (),
    healthy_latency: Mapping[str, int],
    decisions: Sequence[DecisionRecord] = (),
    compute_ms: float = 0.0,
) -> Metrics:
    flows = sorted(flows, key=lambda f: f.id)
    results = allocation.results
    delivered = {f.id: Fraction(results[f.id].delivered) for f in flows}

    # Delivery ratios and unserved traffic
    demand = sum((Fraction(f.rate) for f in flows), Fraction(0))
    total = sum((delivered[f.id] for f in flows), Fraction(0))
    by_class: dict[int, list[Fraction]] = {}
    for f in flows:
        num_den = by_class.setdefault(f.cls, [Fraction(0), Fraction(0)])
        num_den[0] += delivered[f.id]
        num_den[1] += f.rate
    reachable = [f for f in flows if results[f.id].cause != "DISCONNECTED"]
    unserved: dict[str, Fraction] = {}
    for f in flows:
        missing = f.rate - delivered[f.id]
        cause = results[f.id].cause
        if cause != "NONE" and missing > TOLERANCE:
            unserved[cause] = unserved.get(cause, Fraction(0)) + missing

    # Utilization over available arcs, against raw capacity
    up = {l.id for l in topology.links if l.status == "up"}
    arcs = [a for a in all_arcs(topology) if a.link in up]
    load = {a.id: allocation.arc_load.get(a.id, 0) for a in arcs}
    util = {a.id: Fraction(load[a.id], a.capacity) if a.capacity else Fraction(0) for a in arcs}
    over = [a for a in arcs if load[a.id] > a.capacity]
    churn_flows, churn_rate = _churn(previous, allocation, flows)
    link_util = {}
    for link in sorted(topology.links, key=lambda l: l.id):
        values = [util[a.id] for a in arcs if a.link == link.id]
        link_util[link.id] = float(max(values)) if values else 0.0  # a down link shows 0

    return Metrics(
        dr=_ratio(total, demand),
        dr_by_class={cls: _ratio(n, d) for cls, (n, d) in sorted(by_class.items())},
        dr_reach=_ratio(sum((delivered[f.id] for f in reachable), Fraction(0)),
                        sum((Fraction(f.rate) for f in reachable), Fraction(0))),
        unserved_by_cause={cause: float(v) for cause, v in sorted(unserved.items())},
        overloaded_arcs=len(over),
        overload_excess=sum(load[a.id] - a.capacity for a in over),
        max_util=float(max(util.values(), default=Fraction(0))),
        mean_util=float(sum(util.values(), Fraction(0)) / len(util)) if util else 0.0,
        arcs_above_90=sum(1 for u in util.values() if u > ABOVE),
        link_util=link_util,
        latency_stretch=_latency_stretch(topology, flows, allocation, delivered, healthy_latency),
        recovery_ratio=_recovery_ratio(previous, allocation, affected),
        churn_flows=churn_flows,
        churn_rate=churn_rate,
        p0_greedy_gap=float(sum((Fraction(d.greedy_gap) for d in sorted(decisions, key=lambda d: d.flow_id)
                                 if d.cls == 0 and d.greedy_gap is not None), Fraction(0))),
        compute_ms=compute_ms,
    )


def _latency_stretch(topology, flows, allocation, delivered, healthy_latency) -> float:
    """sum(d_f * lat_f) / sum(d_f * lat0_f); lat_f is the rate-weighted latency of the
    flow's paths. Flows with no delivery contribute nothing; 1.0 if nothing is delivered."""
    latency = {a.id: a.latency for a in all_arcs(topology)}
    num = den = Fraction(0)
    for f in flows:
        d = delivered[f.id]
        paths = allocation.results[f.id].paths
        carried = sum(p.rate for p in paths)
        if d <= 0 or not carried:
            continue
        lat_f = Fraction(sum(p.rate * sum(latency[a] for a in p.arcs) for p in paths), carried)
        num += d * lat_f
        den += d * healthy_latency[f.id]
    return _ratio(num, den)


def _recovery_ratio(previous, allocation, affected) -> float | None:
    """Delivered after over delivered before, summed over affected flows. Unset at step 0,
    with no affected flow, or when the affected flows delivered nothing before."""
    affected = sorted(set(affected))
    if previous is None or not affected:
        return None
    before = sum((Fraction(previous.results[f].delivered) for f in affected if f in previous.results), Fraction(0))
    after = sum((Fraction(allocation.results[f].delivered) for f in affected), Fraction(0))
    return float(after / before) if before else None


def _path_set(allocation: Allocation, flow_id: str) -> set[tuple[tuple[str, ...], int]]:
    result = allocation.results.get(flow_id)
    return {(tuple(p.arcs), p.rate) for p in result.paths} if result else set()


def _churn(previous, allocation, flows) -> tuple[int, int]:
    """Flows whose set of (arcs, rate) pairs changed, and the rate on paths of the new
    allocation that were not in the previous one. Step 0 has no churn."""
    if previous is None:
        return 0, 0
    moved = rate = 0
    for f in flows:
        before, after = _path_set(previous, f.id), _path_set(allocation, f.id)
        if before != after:
            moved += 1
            rate += sum(r for _, r in after - before)
    return moved, rate
