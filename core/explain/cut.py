"""Residual cut: the arcs that stop the source reaching the destination (PLAN.md section 10)."""

from collections.abc import Callable, Iterable

from core.explain.data import CutArc
from core.routing.pathfinder import Arc, residual_reachable


def residual_cut(
    post_residuals: Iterable[Arc],
    down_arcs: Iterable[tuple[str, str, str]],
    src: str,
    class_breakdown: Callable[[list[str]], dict[int, int]],
) -> tuple[CutArc, ...]:
    """Arcs leaving the set reachable from `src` over positive-residual arcs, sorted by arc id.

    An available arc in the cut has residual 0 and is `saturated`; an arc of a down link is
    `down` and carries no load.
    """
    post_residuals = list(post_residuals)
    reachable = residual_reachable(post_residuals, src)
    cut = [
        CutArc(arc_id, "saturated", class_breakdown([arc_id]))
        for arc_id, u, v, _ in post_residuals
        if u in reachable and v not in reachable
    ]
    cut += [CutArc(arc_id, "down", {}) for arc_id, u, v in down_arcs if u in reachable and v not in reachable]
    return tuple(sorted(cut, key=lambda c: c.arc))
