"""Resolve TopologySpec and TrafficSpec to concrete inputs (PLAN.md sections 7 and 14).

Templates and generators are looked up by the name in the spec, so a new one is
added by registering it here; callers do not change. An unknown name raises
KeyError naming it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pydantic import TypeAdapter

from core.gen.campus import CAMPUS_PRIMARY_UPLINK
from core.model.types import (
    Flow,
    GeneratedTopologySpec,
    GeneratedTrafficSpec,
    TemplateTopologySpec,
    Topology,
    TopologySpec,
    TrafficSpec,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


@dataclass(frozen=True)
class ResolvedTopology:
    topology: Topology
    primary_uplink: str | None  # link id failed by the path check and scenario 2
    seed: int | None  # seed actually used; differs from the spec's after a generator retry


# template name -> (fixture file under fixtures/topologies/, primary uplink id)
TEMPLATES: dict[str, tuple[str, str | None]] = {
    "campus": ("campus.json", CAMPUS_PRIMARY_UPLINK),
    "diamond": ("diamond.json", None),
}

TOPOLOGY_GENERATORS: dict[str, Callable[[GeneratedTopologySpec], ResolvedTopology]] = {}
TRAFFIC_GENERATORS: dict[str, Callable[[GeneratedTrafficSpec, Topology], list[Flow]]] = {}

_topology_spec = TypeAdapter(TopologySpec)
_traffic_spec = TypeAdapter(TrafficSpec)


def _lookup(table: dict, kind: str, name: str):
    if name not in table:
        raise KeyError(f"unknown {kind} {name!r}; registered: {', '.join(sorted(table)) or 'none'}")
    return table[name]


def resolve_topology(spec: TopologySpec | dict) -> ResolvedTopology:
    spec = _topology_spec.validate_python(spec)
    if isinstance(spec, TemplateTopologySpec):
        filename, uplink = _lookup(TEMPLATES, "template", spec.template)
        topo = Topology.model_validate_json((FIXTURES / "topologies" / filename).read_bytes())
        return ResolvedTopology(topo, uplink, None)
    return _lookup(TOPOLOGY_GENERATORS, "topology generator", spec.generator)(spec)


def resolve_traffic(spec: TrafficSpec | list | dict, topo: Topology) -> list[Flow]:
    spec = _traffic_spec.validate_python(spec)
    if isinstance(spec, GeneratedTrafficSpec):
        return _lookup(TRAFFIC_GENERATORS, "traffic generator", spec.generator)(spec, topo)
    _check_flows(spec, topo)
    return list(spec)  # an explicit list is used as given


def _check_flows(flows: list[Flow], topo: Topology) -> None:
    nodes = {n.id for n in topo.nodes}
    seen: set[str] = set()
    for f in flows:
        if f.id in seen:
            raise ValueError(f"duplicate flow id {f.id!r}")
        seen.add(f.id)
        missing = sorted({f.src, f.dst} - nodes)
        if missing:
            raise ValueError(f"flow {f.id} refers to unknown node: {', '.join(missing)}")
