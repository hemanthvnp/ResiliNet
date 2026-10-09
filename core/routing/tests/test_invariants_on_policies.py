"""A's four policies through B's check_invariants (add-routing-policies and add-decision-explanations, task 7.1).

For each network: step 0 healthy, then step 1 with one link failed and the previous allocation passed
in, as the simulation will call the policies. Every snapshot is built with B's compute_metrics and checked
for I1 to I4, I6, I7, I9 and I11; I8 (two identical runs) and I10 (class isolation) are checked beside it.
"""

import json
import time
from pathlib import Path

import networkx as nx
import pytest
from pydantic import TypeAdapter

from core.gen.campus import DEFAULT_TOPOLOGY, DEFAULT_TRAFFIC
from core.gen.registry import resolve_inputs, resolve_topology, resolve_traffic
from core.gen.tests.headline import with_link_down
from core.metrics.compute import compute_metrics
from core.metrics.invariants import check_invariants, class_isolation, snapshots_identical
from core.model.arcs import available_arcs, parse_arc_id
from core.model.types import Allocation, Flow, PolicyConfig, Snapshot, TemplateTopologySpec, Topology
from core.routing.registry import POLICIES, get_policy

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"
CFG = PolicyConfig()


def healthy_latency(topo: Topology, flows: list[Flow]) -> dict[str, int]:
    """Latency of each flow's shortest path in the healthy network, from a plain networkx query."""
    graph = nx.DiGraph()
    for a in available_arcs(topo):
        if not graph.has_edge(a.src, a.dst) or a.latency < graph[a.src][a.dst]["w"]:
            graph.add_edge(a.src, a.dst, w=a.latency)
    return {
        f.id: nx.shortest_path_length(graph, f.src, f.dst, weight="w")
        for f in flows
        if f.src != f.dst and f.src in graph and f.dst in graph and nx.has_path(graph, f.src, f.dst)
    }


def snapshot(topo: Topology, flows: list[Flow], policy: str, prev: Allocation | None, step: int, latency) -> Snapshot:
    start = time.perf_counter()
    allocation, records = get_policy(policy).route(topo, flows, prev, CFG, step=step)
    ms = (time.perf_counter() - start) * 1000
    down = {link.id for link in topo.links if link.status == "down"}
    affected = sorted(
        f.id for f in flows
        if prev and any(parse_arc_id(a)[0] in down for p in prev.results[f.id].paths for a in p.arcs)
    )
    metrics = compute_metrics(topo, flows, allocation, previous=prev, affected=affected,
                              healthy_latency=latency, decisions=records, compute_ms=ms)
    return Snapshot(step=step, link_state={link.id: link.status for link in topo.links}, allocation=allocation,
                    metrics=metrics, affected_flows=affected, decisions=records)


def sequence(healthy: Topology, failed: Topology, flows: list[Flow], policy: str, latency) -> list[Snapshot]:
    first = snapshot(healthy, flows, policy, None, 0, latency)
    return [first, snapshot(failed, flows, policy, first.allocation, 1, latency)]


def networks() -> dict[str, tuple[Topology, str, list[Flow]]]:
    diamond = Topology.model_validate_json((FIXTURES / "topologies" / "diamond.json").read_text(encoding="utf-8"))
    flows = TypeAdapter(list[Flow])
    out = {
        "diamond": (
            diamond, "L7", flows.validate_json((FIXTURES / "flows" / "diamond.json").read_text(encoding="utf-8"))
        ),
        "diamond fractional": (
            diamond, "L7", flows.validate_json((FIXTURES / "flows" / "s0_fractional.json").read_text(encoding="utf-8"))
        ),
    }
    traffic = json.loads((FIXTURES / "flows" / "campus.json").read_text(encoding="utf-8"))
    template, template_flows = resolve_inputs(TemplateTopologySpec(template="campus"), traffic)
    out["campus template"] = (template.topology, template.primary_uplink or "", template_flows)
    generated = resolve_topology(DEFAULT_TOPOLOGY.model_copy(update={"seed": 100}))
    out["generated seed 100, load 1.0"] = (
        generated.topology,
        generated.primary_uplink or "",
        resolve_traffic(DEFAULT_TRAFFIC.model_copy(update={"load_factor": 1.0}), generated.topology),
    )
    return out


NETWORKS = networks()


@pytest.mark.parametrize("policy", list(POLICIES))
@pytest.mark.parametrize("name", list(NETWORKS))
def test_every_snapshot_satisfies_the_invariants(name, policy):
    topo, uplink, flows = NETWORKS[name]
    failed = with_link_down(topo, uplink)
    latency = healthy_latency(topo, flows)
    first, second = sequence(topo, failed, flows, policy, latency)
    for snap, snap_topo, prev in ((first, topo, None), (second, failed, first.allocation)):
        violations = check_invariants(snap, topology=snap_topo, flows=flows, policy=policy,
                                      healthy_latency=latency, previous=prev, cfg=CFG)
        assert not violations, [str(v) for v in violations]


@pytest.mark.parametrize("policy", list(POLICIES))
def test_two_identical_runs_give_identical_snapshots(policy):
    topo, uplink, flows = NETWORKS["campus template"]
    failed = with_link_down(topo, uplink)
    latency = healthy_latency(topo, flows)
    assert snapshots_identical(sequence(topo, failed, flows, policy, latency),
                               sequence(topo, failed, flows, policy, latency))


@pytest.mark.parametrize("name", list(NETWORKS))
def test_s2_class_isolation(name):
    topo, uplink, flows = NETWORKS[name]
    for network in (topo, with_link_down(topo, uplink)):
        assert class_isolation(get_policy("S2"), network, flows, CFG) == []


def test_the_checker_names_a_broken_policy_snapshot():
    """The check is not vacuous: breaking a real S2 snapshot is reported under the right invariant."""
    topo, _, flows = NETWORKS["diamond"]
    latency = healthy_latency(topo, flows)
    broken = snapshot(topo, flows, "S2", None, 0, latency).model_dump()
    broken["allocation"]["arc_load"]["L2:A>B"] += 1
    found = {v.invariant for v in check_invariants(Snapshot.model_validate(broken), topology=topo, flows=flows,
                                                   policy="S2", healthy_latency=latency, cfg=CFG)}
    assert {"I4", "I6"} <= found
