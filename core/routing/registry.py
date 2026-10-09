"""Policies selectable by name (PLAN.md section 14). The callables work on plain inputs;
the adapter over core/model types wraps them once B's contract is merged."""

from collections.abc import Callable
from dataclasses import replace

from core.routing.allocator import allocate
from core.routing.baselines import route_s0, route_s0_qos
from core.routing.inputs import AllocConfig, RouteResult


def route_s1(arcs, flows, cfg: AllocConfig | None = None, **kwargs) -> RouteResult:
    """S1: arrival order, one path, latency-only cost. Only `util_cap` is read from `cfg`."""
    cfg = cfg or AllocConfig()
    return allocate(arcs, flows, replace(cfg, order="arrival", max_paths=1, congestion_lambda=0), **kwargs)


def route_s2(arcs, flows, cfg: AllocConfig | None = None, **kwargs) -> RouteResult:
    """S2: the allocator exactly as configured (class-first order and splitting by default)."""
    return allocate(arcs, flows, cfg or AllocConfig(), **kwargs)


POLICIES: dict[str, Callable[..., RouteResult]] = {
    "S0": route_s0,
    "S0-QoS": route_s0_qos,
    "S1": route_s1,
    "S2": route_s2,
}


def get_policy(name: str) -> Callable[..., RouteResult]:
    try:
        return POLICIES[name]
    except KeyError:
        raise ValueError(f"unknown policy {name!r}; expected one of {sorted(POLICIES)}") from None
