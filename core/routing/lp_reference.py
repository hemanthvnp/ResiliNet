"""LP reference: a fractional upper bound on what any routing can deliver (PLAN.md section 3).

This is offline analysis, not a policy. Flows may be split over any number of paths, in any
fraction, so no integer, path-limited or greedy allocation (S1, S2) can deliver more. It needs
scipy, which is optional and imported only when `lp_upper_bound` is called.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from core.model.arcs import available_arcs
from core.model.ledger import effective_capacity
from core.model.types import Flow, PolicyConfig, Topology
from core.routing.checks import validate_inputs


@dataclass(frozen=True)
class LpBound:
    """Fractional upper bounds, in Mbps."""

    total: float  # most that all flows together can deliver
    by_class: dict[int, float]  # most each class can deliver if it were alone in the network


def lp_upper_bound(topo: Topology, flows: Sequence[Flow], util_cap: float = 1.0) -> LpBound:
    """Fractional upper bound on delivered traffic, from a multi-commodity flow LP (HiGHS).

    One variable per (flow, available arc) plus the delivered amount of each flow, with flow
    conservation per flow and node and `sum of flows <= floor(util_cap * capacity)` per arc.
    The bound is on total delivery, and for each class on its delivery alone in the network;
    both hold for S2 whatever its order, because S2's class isolation makes a class's result
    independent of the lower ones and no allocation can beat the LP.
    """
    import numpy as np
    from scipy.optimize import linprog
    from scipy.sparse import coo_matrix

    validate_inputs(flows, PolicyConfig(util_cap=util_cap))
    available = available_arcs(topo)
    capacity = [effective_capacity(a.capacity, util_cap) for a in available]
    endpoints = {f.src for f in flows} | {f.dst for f in flows}
    nodes = sorted({a.src for a in available} | {a.dst for a in available} | endpoints)
    node_index = {n: i for i, n in enumerate(nodes)}

    free = sum(f.rate for f in flows if f.src == f.dst)  # needs no network
    routed = sorted((f for f in flows if f.src != f.dst and f.rate > 0), key=lambda f: f.id)
    by_class_free: dict[int, float] = {}
    for f in flows:
        if f.src == f.dst:
            by_class_free[f.cls] = by_class_free.get(f.cls, 0.0) + f.rate
    classes = sorted({f.cls for f in flows})
    if not routed:
        return LpBound(float(free), {c: by_class_free.get(c, 0.0) for c in classes})

    n_arcs, n_flows = len(available), len(routed)
    n_vars = n_flows * (n_arcs + 1)  # per flow: one variable per arc, then its delivered amount

    def x(flow: int, arc: int) -> int:
        return flow * (n_arcs + 1) + arc

    def delivered(flow: int) -> int:
        return flow * (n_arcs + 1) + n_arcs

    eq_rows, eq_cols, eq_vals = [], [], []
    for i, f in enumerate(routed):
        for j, a in enumerate(available):
            eq_rows += [i * len(nodes) + node_index[a.src], i * len(nodes) + node_index[a.dst]]
            eq_cols += [x(i, j), x(i, j)]
            eq_vals += [1.0, -1.0]  # leaves u, enters v
        eq_rows += [i * len(nodes) + node_index[f.src], i * len(nodes) + node_index[f.dst]]
        eq_cols += [delivered(i), delivered(i)]
        eq_vals += [-1.0, 1.0]  # out - in = d at the source, = -d at the destination
    a_eq = coo_matrix((eq_vals, (eq_rows, eq_cols)), shape=(n_flows * len(nodes), n_vars)).tocsr()

    ub_rows = [j for i in range(n_flows) for j in range(n_arcs)]
    ub_cols = [x(i, j) for i in range(n_flows) for j in range(n_arcs)]
    a_ub = coo_matrix(([1.0] * len(ub_rows), (ub_rows, ub_cols)), shape=(n_arcs, n_vars)).tocsr()

    bounds: list[tuple[float, float | None]] = [(0.0, None)] * n_vars
    for i, f in enumerate(routed):
        bounds[delivered(i)] = (0.0, float(f.rate))

    def solve(selected: Sequence[int]) -> float:
        cost = np.zeros(n_vars)
        for i in selected:
            cost[delivered(i)] = -1.0  # linprog minimises
        result = linprog(cost, A_ub=a_ub, b_ub=np.array(capacity, dtype=float), A_eq=a_eq,
                         b_eq=np.zeros(n_flows * len(nodes)), bounds=bounds, method="highs")
        if result.status != 0:
            raise RuntimeError(f"LP reference failed: {result.message}")
        return float(-result.fun)

    total = solve(range(n_flows)) + free
    by_class = {
        c: solve([i for i, f in enumerate(routed) if f.cls == c]) + by_class_free.get(c, 0.0) for c in classes
    }
    return LpBound(total, by_class)
