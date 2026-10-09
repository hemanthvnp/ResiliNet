"""Max-flow bound and greedy gap (PLAN.md section 5, add-decision-explanations)."""

from collections.abc import Iterable

from core.routing.inputs import PathRate
from core.routing.pathfinder import Arc, max_flow_value


def maxflow_bound(
    post_residuals: Iterable[Arc], own_paths: Iterable[PathRate], src: str, dst: str, rate: int
) -> int:
    """min(rate, max flow) on the residuals as they were before this flow was placed.

    `post_residuals` are the residuals after the flow's placement; its own reservations are
    added back to get the state it started from.
    """
    own: dict[str, int] = {}
    for path in own_paths:
        for arc_id in path.arcs:
            own[arc_id] = own.get(arc_id, 0) + path.rate
    pre = [(arc_id, u, v, residual + own.get(arc_id, 0)) for arc_id, u, v, residual in post_residuals]
    return min(rate, max_flow_value(pre, src, dst))


def greedy_gap(bound: int, delivered: float) -> float:
    """What the flow could have had but did not get. Never negative by construction."""
    return float(bound - delivered)
