"""Resolve TopologySpec and TrafficSpec to concrete inputs (PLAN.md sections 7, 9 and 14).

Templates and generators are looked up by the name in the spec, so a new one is
added by registering it here; callers do not change. An unknown name raises
KeyError naming it.

`resolve_inputs` is the checked entry point: for a generated topology it runs the
post-failure path check together with the traffic and retries with the next seed.
`resolve_topology` on a generator spec alone generates without that check, since it
has no traffic to check against.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from pydantic import TypeAdapter

from core.gen.campus import CAMPUS_PRIMARY_UPLINK, generate_campus
from core.gen.pathcheck import PathCheckReport, check_post_failure
from core.gen.resolved import ResolvedTopology
from core.gen.traffic import generate_traffic
from core.model.types import (
    Flow,
    GeneratedTopologySpec,
    GeneratedTrafficSpec,
    TemplateTopologySpec,
    Topology,
    TopologySpec,
    TrafficSpec,
)

__all__ = ["ResolvedTopology", "resolve_inputs", "resolve_topology", "resolve_traffic"]

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
MAX_ATTEMPTS = 20  # PLAN.md section 9

# template name -> (fixture file under fixtures/topologies/, primary uplink id)
TEMPLATES: dict[str, tuple[str, str | None]] = {
    "campus": ("campus.json", CAMPUS_PRIMARY_UPLINK),
    "diamond": ("diamond.json", None),
    "congestion": ("congestion.json", None),  # scenario 4
    "line": ("line.json", None),  # scenario 5
}

TOPOLOGY_GENERATORS: dict[str, Callable[[GeneratedTopologySpec], ResolvedTopology]] = {
    "campus": generate_campus,
}
TRAFFIC_GENERATORS: dict[str, Callable[[GeneratedTrafficSpec, Topology], list[Flow]]] = {
    "campus": generate_traffic,
}

_topology_spec = TypeAdapter(TopologySpec)
_traffic_spec = TypeAdapter(TrafficSpec)

Check = Callable[[Topology, list[Flow], str], PathCheckReport]


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


def resolve_inputs(topology_spec: TopologySpec | dict, traffic_spec: TrafficSpec | list | dict,
                   check: Check = check_post_failure) -> tuple[ResolvedTopology, list[Flow]]:
    """Topology and traffic together. A generated topology must pass the post-failure
    path check on its primary uplink; on failure the next seed is tried, at most
    MAX_ATTEMPTS seeds in all (seed, seed + 1, ...), then RuntimeError. The traffic
    seed does not change. The seed actually used is in the returned ResolvedTopology."""
    topology_spec = _topology_spec.validate_python(topology_spec)
    if isinstance(topology_spec, TemplateTopologySpec):
        resolved = resolve_topology(topology_spec)
        return resolved, resolve_traffic(traffic_spec, resolved.topology)

    last = None
    for attempt in range(MAX_ATTEMPTS):
        seeded = topology_spec.model_copy(update={"seed": topology_spec.seed + attempt})
        resolved = resolve_topology(seeded)
        flows = resolve_traffic(traffic_spec, resolved.topology)
        last = check(resolved.topology, flows, resolved.primary_uplink)
        if not last.failures:
            return resolved, flows
    raise RuntimeError(
        f"no seed from {topology_spec.seed} to {topology_spec.seed + MAX_ATTEMPTS - 1} passes the "
        f"post-failure path check; last failure: {last.failures[0]}"
    )


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
