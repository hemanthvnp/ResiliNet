"""The four policies as RoutingPolicy objects, selectable by name (PLAN.md sections 7 and 14)."""

from collections.abc import Sequence

from core.model.types import Allocation, DecisionRecord, Flow, PolicyConfig, RoutingPolicy, Topology
from core.routing.allocator import allocate
from core.routing.baselines import route_s0, route_s0_qos

Result = tuple[Allocation, list[DecisionRecord]]


class S0:
    """Latency-shortest path, no admission control, proportional loss."""

    name = "S0"

    def route(
        self, topo: Topology, flows: Sequence[Flow], prev: Allocation | None, cfg: PolicyConfig, *, step: int = 0
    ) -> Result:
        return route_s0(topo, flows, prev, cfg, step=step)


class S0QoS:
    """The S0 routes with strict priority on each arc."""

    name = "S0-QoS"

    def route(
        self, topo: Topology, flows: Sequence[Flow], prev: Allocation | None, cfg: PolicyConfig, *, step: int = 0
    ) -> Result:
        return route_s0_qos(topo, flows, prev, cfg, step=step)


class S1:
    """Arrival order, one path, latency-only cost. Only `util_cap` is read from the config."""

    name = "S1"

    def route(
        self, topo: Topology, flows: Sequence[Flow], prev: Allocation | None, cfg: PolicyConfig, *, step: int = 0
    ) -> Result:
        s1 = cfg.model_copy(update={"order": "arrival", "max_paths": 1, "congestion_lambda": 0})
        return allocate(topo, flows, prev, s1, step=step)


class S2:
    """The allocator exactly as configured (class-first order and splitting by default)."""

    name = "S2"

    def route(
        self, topo: Topology, flows: Sequence[Flow], prev: Allocation | None, cfg: PolicyConfig, *, step: int = 0
    ) -> Result:
        return allocate(topo, flows, prev, cfg, step=step)


POLICIES: dict[str, RoutingPolicy] = {p.name: p for p in (S0(), S0QoS(), S1(), S2())}


def get_policy(name: str) -> RoutingPolicy:
    try:
        return POLICIES[name]
    except KeyError:
        raise ValueError(f"unknown policy {name!r}; expected one of {sorted(POLICIES)}") from None
