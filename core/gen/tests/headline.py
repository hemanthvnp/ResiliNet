"""H8 headline check (PLAN.md section 12, task 4.1 of add-network-generators).

Runs S0, S0-QoS and S2 through the routing registry on the campus template, healthy
and with the primary uplink failed, and reports DR, DR by class and overloaded arcs.
It lives in B's folder and only calls A's public RoutingPolicy interface.

Run:  python -m core.gen.tests.headline
"""

from __future__ import annotations

import json
from collections import defaultdict

from core.gen.campus import CAMPUS_PRIMARY_UPLINK
from core.gen.registry import FIXTURES, resolve_inputs
from core.model.arcs import all_arcs
from core.model.types import Allocation, Flow, PolicyConfig, TemplateTopologySpec, Topology
from core.routing.registry import get_policy

POLICIES = ("S0", "S0-QoS", "S2")


def with_link_down(topo: Topology, link_id: str) -> Topology:
    return topo.model_copy(update={"links": [
        l.model_copy(update={"status": "down"}) if l.id == link_id else l for l in topo.links
    ]})


def delivery_ratios(flows: list[Flow], alloc: Allocation) -> dict[str, float]:
    """DR overall and per class (PLAN.md section 8), from delivered over demand."""
    demand, delivered = defaultdict(int), defaultdict(float)
    for f in flows:
        demand[f.cls] += f.rate
        delivered[f.cls] += alloc.results[f.id].delivered
    ratios = {"DR": sum(delivered.values()) / sum(demand.values())}
    ratios.update({f"DR_P{cls}": delivered[cls] / demand[cls] for cls in sorted(demand)})
    return ratios


def overloaded_arcs(topo: Topology, alloc: Allocation) -> int:
    capacity = {a.id: a.capacity for a in all_arcs(topo)}
    return sum(1 for arc, load in alloc.arc_load.items() if load > capacity[arc])


def run(failed_link: str | None = CAMPUS_PRIMARY_UPLINK) -> dict[str, dict[str, float]]:
    traffic = json.loads((FIXTURES / "flows" / "campus.json").read_text())
    resolved, flows = resolve_inputs(TemplateTopologySpec(template="campus"), traffic)
    topo = with_link_down(resolved.topology, failed_link) if failed_link else resolved.topology
    rows = {}
    for name in POLICIES:
        alloc, _ = get_policy(name).route(topo, flows, None, PolicyConfig())
        rows[name] = {**delivery_ratios(flows, alloc), "overloaded_arcs": overloaded_arcs(topo, alloc)}
    return rows


def main() -> None:
    for label, failed in (("healthy", None), (f"{CAMPUS_PRIMARY_UPLINK} failed", CAMPUS_PRIMARY_UPLINK)):
        print(f"campus template, {label}")
        for name, row in run(failed).items():
            cells = "  ".join(f"{k} {v:.4f}" if isinstance(v, float) else f"{k} {v}" for k, v in row.items())
            print(f"  {name:<8} {cells}")


if __name__ == "__main__":
    main()
