"""Directed-arc view of a topology (PLAN.md sections 4 and 7).

Each physical link {u, v} is two arcs, one per direction, each with the link's
capacity and latency. An arc is available iff its link is up. Arc ids have the
form "<link id>:<from>><to>" (for example "L7:B>D"); no other module builds one.
Every list returned here is sorted by arc id.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.model.types import Link, Topology


@dataclass(frozen=True)
class Arc:
    id: str
    link: str
    src: str
    dst: str
    capacity: int
    latency: int


def arc_id(link_id: str, src: str, dst: str) -> str:
    return f"{link_id}:{src}>{dst}"


def parse_arc_id(arc: str) -> tuple[str, str, str]:
    """Return (link id, from node, to node). Raises ValueError on a malformed id."""
    link_id, sep, ends = arc.rpartition(":")
    src, sep2, dst = ends.partition(">")
    if not (sep and sep2 and link_id and src and dst) or ">" in dst:
        raise ValueError(f"malformed arc id: {arc!r}")
    return link_id, src, dst


def link_arcs(link: Link) -> tuple[Arc, Arc]:
    """Both arcs of a link, regardless of its status, sorted by arc id."""
    if link.u == link.v:
        raise ValueError(f"link {link.id} is a self-loop")
    for node in (link.u, link.v):
        if ":" in node or ">" in node:
            raise ValueError(f"node id {node!r} on link {link.id} contains ':' or '>'")
    forward = Arc(arc_id(link.id, link.u, link.v), link.id, link.u, link.v, link.capacity, link.latency)
    backward = Arc(arc_id(link.id, link.v, link.u), link.id, link.v, link.u, link.capacity, link.latency)
    return (forward, backward) if forward.id < backward.id else (backward, forward)


def all_arcs(topo: Topology) -> list[Arc]:
    """Every arc of every link, up or down, sorted by arc id."""
    return sorted((a for link in topo.links for a in link_arcs(link)), key=lambda a: a.id)


def available_arcs(topo: Topology) -> list[Arc]:
    """Arcs of links whose status is up, sorted by arc id."""
    return sorted(
        (a for link in topo.links if link.status == "up" for a in link_arcs(link)),
        key=lambda a: a.id,
    )
