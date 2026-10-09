"""Single-link sensitivity sweep (change criticality-sweep; PLAN-CYCLE2.md section 3.2).

For each policy, one Simulation starts healthy (step 0, the scenario's own events ignored);
each link in ascending id order is failed alone, measured, and the healthy state restored.

Two groups, both always reported:
    structural   bridges of the healthy topology: failing one disconnects part of the network
    operational  every other link, ranked by lowest post-failure DR_P0, then lowest DR

Exact ties share a rank (1, 1, 3); link id only orders rows. Absolute post-failure values and
drops from the healthy value are reported side by side. A scenario with no P0 flows has no
DR_P0: the cell is empty and ranking falls back to DR.
"""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import networkx as nx

from core.model.types import Event, Snapshot, Topology
from core.sim.simulation import Simulation

COLUMNS = ["policy", "group", "rank", "link_id", "dr_p0", "dr", "dr_p0_drop", "dr_drop",
           "overloaded_arcs", "unreachable_demand"]
GROUPS = ("structural", "operational")


@dataclass(frozen=True)
class Row:
    policy: str
    group: str
    rank: int
    link_id: str
    dr_p0: float | None
    dr: float
    dr_p0_drop: float | None
    dr_drop: float
    overloaded_arcs: int
    unreachable_demand: float


def link_order(link_id: str) -> tuple:
    """L2 before L10: digits compare as numbers."""
    return tuple(int(p) if p.isdigit() else p for p in re.split(r"(\d+)", link_id))


def bridges(topology: Topology) -> set[str]:
    """Links whose failure splits the healthy topology. A bridge between two nodes joined by
    more than one link is not one, since the parallel link keeps them connected."""
    up = [l for l in topology.links if l.status == "up"]
    graph = nx.Graph()
    graph.add_nodes_from(sorted(n.id for n in topology.nodes))
    graph.add_edges_from(sorted((l.u, l.v) for l in up))
    by_pair: dict[frozenset, list[str]] = {}
    for l in up:
        by_pair.setdefault(frozenset((l.u, l.v)), []).append(l.id)
    return {ids[0] for u, v in nx.bridges(graph) if len(ids := by_pair[frozenset((u, v))]) == 1}


def competition_ranks(keys: Sequence[tuple]) -> list[int]:
    """1-based ranks of `keys` in ascending order; equal keys share a rank (1, 1, 3)."""
    ordered = sorted(keys)
    return [ordered.index(k) + 1 for k in keys]


def _dr_p0(snapshot: Snapshot) -> float | None:
    return snapshot.metrics.dr_by_class.get(0)


def sweep_policy(new_simulation: Callable[[str], Simulation], policy: str) -> list[Row]:
    sim = new_simulation(policy)
    healthy = sim.snapshot
    structural = bridges(sim.topology)
    measured = []  # (link id, post-failure snapshot)
    for link in sorted((l.id for l in sim.topology.links), key=link_order):
        measured.append((link, sim.apply(Event(step=1, kind="fail", links=[link]))))
        sim.reset()
    h_p0, h_dr = _dr_p0(healthy), healthy.metrics.dr
    rows = []
    for group in GROUPS:
        members = [(l, s) for l, s in measured if (l in structural) == (group == "structural")]
        keys = [(_dr_p0(s) if _dr_p0(s) is not None else 0.0, s.metrics.dr) for _, s in members]
        for (link, snap), rank in zip(members, competition_ranks(keys)):
            p0 = _dr_p0(snap)
            rows.append(Row(
                policy=policy, group=group, rank=rank, link_id=link, dr_p0=p0, dr=snap.metrics.dr,
                dr_p0_drop=None if p0 is None or h_p0 is None else h_p0 - p0, dr_drop=h_dr - snap.metrics.dr,
                overloaded_arcs=snap.metrics.overloaded_arcs,
                unreachable_demand=snap.metrics.unserved_by_cause.get("DISCONNECTED", 0.0),
            ))
    return rows


def sweep(new_simulation: Callable[[str], Simulation], policies: Sequence[str]) -> list[Row]:
    """Every (policy, link) row, sorted by policy name, group (structural first), rank, link id."""
    rows = [row for policy in policies for row in sweep_policy(new_simulation, policy)]
    return sorted(rows, key=lambda r: (r.policy, GROUPS.index(r.group), r.rank, link_order(r.link_id)))


def to_csv(rows: Sequence[Row]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(COLUMNS)
    for r in rows:
        writer.writerow(["" if (v := getattr(r, c)) is None else v for c in COLUMNS])
    return out.getvalue()


def summary(rows: Sequence[Row], top: int = 5) -> str:
    """Per policy: every structural link, then the operational links ranked 1 to `top`."""
    lines = []
    for policy in sorted({r.policy for r in rows}):
        lines.append(f"{policy}")
        lines.append(f"  {'group':<11} {'rank':>4}  {'link':<6} {'DR_P0':>6} {'DR':>6} {'P0 drop':>8} {'DR drop':>8} "
                     f"{'overld':>6} {'unreach':>7}")
        for r in rows:
            if r.policy == policy and (r.group == "structural" or r.rank <= top):
                p0 = "-" if r.dr_p0 is None else f"{r.dr_p0:.3f}"
                p0d = "-" if r.dr_p0_drop is None else f"{r.dr_p0_drop:.3f}"
                lines.append(f"  {r.group:<11} {r.rank:>4}  {r.link_id:<6} {p0:>6} {r.dr:>6.3f} {p0d:>8} "
                             f"{r.dr_drop:>8.3f} {r.overloaded_arcs:>6} {r.unreachable_demand:>7g}")
    return "\n".join(lines)
