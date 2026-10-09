"""Graph algorithms for routing. The only module under core/routing that may import networkx.

Arcs are passed as plain tuples so this module does not depend on core/model:
    (arc_id, src_node, dst_node, value)
where value is the integer weight, residual or capacity, depending on the function.
"""

import heapq
from collections import deque
from collections.abc import Iterable
from typing import NamedTuple

import networkx as nx

Arc = tuple[str, str, str, int]


class Path(NamedTuple):
    cost: int
    nodes: tuple[str, ...]
    arcs: tuple[str, ...]


def shortest_path(arcs: Iterable[Arc], src: str, dst: str) -> Path | None:
    """Minimum-cost simple path, ties broken by (cost, hops, node ids), then arc ids.

    Heap labels are the full (cost, hops, nodes, arcs) tuple. Extending a path by one arc
    keeps the order of two paths to the same node, so the first label popped for a node is
    its best one, and the result does not depend on the order of `arcs`.
    """
    out: dict[str, list[Arc]] = {}
    for arc in sorted(arcs):
        if arc[3] < 0:
            raise ValueError(f"negative weight on arc {arc[0]}")
        out.setdefault(arc[1], []).append(arc)

    heap: list[tuple[int, int, tuple[str, ...], tuple[str, ...]]] = [(0, 0, (src,), ())]
    done: set[str] = set()
    while heap:
        cost, hops, nodes, arc_ids = heapq.heappop(heap)
        node = nodes[-1]
        if node in done:
            continue
        done.add(node)
        if node == dst:
            return Path(cost, nodes, arc_ids)
        for arc_id, _, nxt, weight in out.get(node, ()):
            if nxt not in done:
                heapq.heappush(heap, (cost + weight, hops + 1, nodes + (nxt,), arc_ids + (arc_id,)))
    return None


def connected_components(nodes: Iterable[str], arcs: Iterable[Arc]) -> list[tuple[str, ...]]:
    """Components of the available graph, each sorted, ordered by first node.

    `nodes` is passed so that a node with no available arc is its own component.
    """
    graph = nx.Graph()
    graph.add_nodes_from(sorted(nodes))
    graph.add_edges_from((u, v) for _, u, v, _ in sorted(arcs))
    return sorted(tuple(sorted(c)) for c in nx.connected_components(graph))


def residual_reachable(arcs: Iterable[Arc], src: str) -> frozenset[str]:
    """Nodes reachable from `src` over arcs whose residual (the value field) is above zero."""
    out: dict[str, list[str]] = {}
    for _, u, v, residual in sorted(arcs):
        if residual > 0:
            out.setdefault(u, []).append(v)
    seen = {src}
    queue = deque([src])
    while queue:
        for nxt in out.get(queue.popleft(), ()):
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return frozenset(seen)


def max_flow_value(arcs: Iterable[Arc], src: str, dst: str) -> int:
    """Maximum flow from `src` to `dst` for integer arc capacities (the value field)."""
    if src == dst:
        raise ValueError("max flow needs distinct source and destination")
    graph = nx.DiGraph()
    for _, u, v, capacity in sorted(arcs):
        if graph.has_edge(u, v):
            graph[u][v]["capacity"] += capacity
        else:
            graph.add_edge(u, v, capacity=capacity)
    if src not in graph or dst not in graph:
        return 0
    return int(nx.maximum_flow_value(graph, src, dst))
