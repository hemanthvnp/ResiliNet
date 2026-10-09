"""Post-failure path check (PLAN.md section 9, assumption A1).

On a copy of the topology with the primary uplink failed, every node of type
`building` must have at least two node-disjoint paths to the core (any node of type
`core`), and a combined capacity strictly above its P0 plus P1 demand. Combined
capacity is the max-flow value from the building to the core; it does not depend
on which disjoint paths a search happens to return. Hostels and services are not
checked. One definition, used by the template test and by the generator.
"""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx
from networkx.algorithms.connectivity import local_node_connectivity

from core.model.types import Flow, Topology

CHECKED_TYPE = "building"
CORE_TYPE = "core"
CHECKED_CLASSES = (0, 1)
_SINK = ("__core__",)  # a tuple, so it cannot collide with a string node id


@dataclass(frozen=True)
class BuildingCheck:
    building: str
    disjoint_paths: int
    capacity: int
    demand: int

    @property
    def passed(self) -> bool:
        return self.disjoint_paths >= 2 and self.capacity > self.demand


@dataclass(frozen=True)
class Failure:
    building: str
    reason: str

    def __str__(self) -> str:
        return f"{self.building}: {self.reason}"


@dataclass(frozen=True)
class PathCheckReport:
    uplink: str
    buildings: dict[str, BuildingCheck]  # by building id, sorted
    failures: list[Failure]  # in building id order

    @property
    def passed(self) -> bool:
        return not self.failures


def check_post_failure(topo: Topology, flows: list[Flow], uplink: str) -> PathCheckReport:
    if uplink not in {l.id for l in topo.links}:
        raise KeyError(f"uplink {uplink!r} is not a link of this topology")
    graph = _graph_without(topo, uplink)

    demand: dict[str, int] = {}
    for f in flows:
        if f.cls in CHECKED_CLASSES:
            for end in {f.src, f.dst}:
                demand[end] = demand.get(end, 0) + f.rate

    buildings: dict[str, BuildingCheck] = {}
    failures: list[Failure] = []
    for b in sorted(n.id for n in topo.nodes if n.type == CHECKED_TYPE):
        paths = local_node_connectivity(graph, b, _SINK) if b in graph else 0
        capacity = int(nx.maximum_flow_value(graph, b, _SINK)) if paths else 0
        check = BuildingCheck(b, paths, capacity, demand.get(b, 0))
        buildings[b] = check
        if check.disjoint_paths < 2:
            failures.append(Failure(b, f"{check.disjoint_paths} node-disjoint path(s) to the core "
                                       f"after {uplink} fails; need 2"))
        elif not check.capacity > check.demand:
            failures.append(Failure(b, f"capacity {check.capacity} to the core after {uplink} fails "
                                       f"does not exceed P0+P1 demand {check.demand}"))
    return PathCheckReport(uplink, buildings, failures)


def _graph_without(topo: Topology, uplink: str) -> nx.DiGraph:
    """Directed graph of the up links other than `uplink`, with a sink fed by every core
    node. Parallel links add their capacities. The input topology is not changed."""
    graph = nx.DiGraph()
    graph.add_nodes_from(sorted(n.id for n in topo.nodes))
    for link in sorted(topo.links, key=lambda l: l.id):
        if link.status != "up" or link.id == uplink:
            continue
        for a, b in ((link.u, link.v), (link.v, link.u)):
            cap = graph[a][b]["capacity"] + link.capacity if graph.has_edge(a, b) else link.capacity
            graph.add_edge(a, b, capacity=cap)
    graph.add_node(_SINK)
    for core in sorted(n.id for n in topo.nodes if n.type == CORE_TYPE):
        graph.add_edge(core, _SINK)  # no capacity attribute: unbounded
    return graph
