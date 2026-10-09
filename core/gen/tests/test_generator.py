"""Seeded campus generator, checked resolution with retry, and load scaling.

Expected values are the hand-worked numbers confirmed by B (Group 3 of
add-network-generators): T1 to T6, the retry rules, and S1 to S4.
"""

import json
from collections import Counter
from pathlib import Path

import networkx as nx
import pytest

from core.gen.campus import (
    DEFAULT_TOPOLOGY,
    DEFAULT_TRAFFIC,
    distribution_count,
    generate_campus,
    uplink_capacities,
)
from core.gen.pathcheck import Failure, PathCheckReport
from core.gen.registry import resolve_inputs, resolve_topology, resolve_traffic
from core.gen.traffic import scale_flows
from core.model.types import Flow, GeneratedTopologySpec, TemplateTopologySpec

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"


def spec(buildings=37, redundancy=0.5, seed=1):
    return GeneratedTopologySpec(generator="campus", buildings=buildings, redundancy=redundancy, seed=seed)


def types_of(topo):
    return Counter(n.type for n in topo.nodes)


# Shape: T1 to T6

def test_default_size_is_50_nodes():  # T1
    topo = generate_campus(spec()).topology
    assert len(topo.nodes) == 50
    assert types_of(topo) == {"core": 2, "service": 4, "distribution": 5, "building": 37, "hostel": 2}


@pytest.mark.parametrize("redundancy, links", [(0.0, 91), (1.0, 128)])  # T2, T3
def test_link_count_by_redundancy(redundancy, links):
    assert len(generate_campus(spec(redundancy=redundancy)).topology.links) == links


@pytest.mark.parametrize("buildings, expected", [(37, 5), (5, 2), (16, 2), (17, 3)])  # T1, T4
def test_distribution_count(buildings, expected):
    assert distribution_count(buildings) == expected


@pytest.mark.parametrize("primaries, hostels, expected", [(8, 1, (170, 85)), (0, 0, (20, 10))])  # T5, T6
def test_uplink_capacities(primaries, hostels, expected):
    assert uplink_capacities(primaries, hostels) == expected


def test_primary_uplink_is_l6_from_first_distribution_to_first_core():
    resolved = generate_campus(spec())
    types = {n.id: n.type for n in resolved.topology.nodes}
    l6 = next(l for l in resolved.topology.links if l.id == "L6")
    assert resolved.primary_uplink == "L6"
    assert (l6.u, l6.v) == ("N3", "N1")
    assert (types["N3"], types["N1"]) == ("distribution", "core")


def test_every_building_has_two_uplinks_to_different_distribution_nodes():
    topo = generate_campus(spec(redundancy=0.0)).topology
    types = {n.id: n.type for n in topo.nodes}
    for b in (n.id for n in topo.nodes if n.type == "building"):
        ends = sorted(l.v if l.u == b else l.u for l in topo.links if b in (l.u, l.v))
        assert len(ends) == 2 and ends[0] != ends[1], b
        assert all(types[e] == "distribution" for e in ends), b


def test_services_keep_fixed_ids():
    ids = {n.id for n in generate_campus(spec()).topology.nodes if n.type == "service"}
    assert ids == {"AUTH", "EMRG", "LMS", "INET"}


# Properties for any seed (task 5.1)

def test_same_seed_same_json():
    assert generate_campus(spec(seed=4)).topology.model_dump_json() == \
        generate_campus(spec(seed=4)).topology.model_dump_json()


def test_different_seeds_differ():
    assert generate_campus(spec(seed=1)).topology != generate_campus(spec(seed=2)).topology


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_generated_network_is_connected(seed):
    topo = generate_campus(spec(seed=seed)).topology
    g = nx.Graph()
    g.add_nodes_from(n.id for n in topo.nodes)
    g.add_edges_from((l.u, l.v) for l in topo.links if l.status == "up")
    assert nx.is_connected(g)
    assert all(isinstance(l.capacity, int) and isinstance(l.latency, int) for l in topo.links)


@pytest.mark.parametrize("bad", [dict(buildings=0), dict(redundancy=-0.1), dict(redundancy=1.5)])
def test_invalid_parameters_are_rejected(bad):
    with pytest.raises(ValueError):
        generate_campus(spec(**bad))


def test_resolve_topology_dispatches_to_the_generator():
    assert resolve_topology(spec()).topology == generate_campus(spec()).topology


# Checked resolution with retry (section 9)

def report(failures):
    return PathCheckReport("L6", {}, [Failure(b, "test failure") for b in failures])


def test_default_spec_passes_the_check():  # task 5.4
    resolved, flows = resolve_inputs(DEFAULT_TOPOLOGY, DEFAULT_TRAFFIC)
    assert len(resolved.topology.nodes) == 50
    assert len(flows) == 200
    assert resolved.seed is not None


def test_retry_reports_the_effective_seed():
    seen = []

    def fails_once(topo, flows, uplink):
        seen.append(uplink)
        return report(["N9"] if len(seen) == 1 else [])

    resolved, _ = resolve_inputs(spec(seed=10), DEFAULT_TRAFFIC, check=fails_once)
    assert resolved.seed == 11
    assert resolved.topology == generate_campus(spec(seed=11)).topology
    assert seen == ["L6", "L6"]


def test_retries_exhausted_after_20_attempts():
    calls = []

    def always_fails(topo, flows, uplink):
        calls.append(1)
        return report([f"N{len(calls)}"])

    with pytest.raises(RuntimeError, match="N20"):
        resolve_inputs(spec(seed=5), DEFAULT_TRAFFIC, check=always_fails)
    assert len(calls) == 20


def test_template_inputs_are_returned_without_retry():
    traffic = json.loads((FIXTURES / "flows" / "campus.json").read_text())
    resolved, flows = resolve_inputs(TemplateTopologySpec(template="campus"), traffic)
    assert resolved.seed is None
    assert len(flows) == 19


# Load scaling (task 5.3)

FLOWS = [Flow(id="F1", src="B1", dst="AUTH", rate=2, cls=0, service="auth"),
         Flow(id="F2", src="B1", dst="LMS", rate=8, cls=1, service="lms"),
         Flow(id="F3", src="B1", dst="INET", rate=5, cls=2, service="internet")]


@pytest.mark.parametrize("factor, rates", [(1.5, [3, 12, 8]), (1.0, [2, 8, 5]), (0.1, [1, 1, 1])])  # S1-S3
def test_scaling(factor, rates):
    scaled = scale_flows(FLOWS, factor)
    assert [f.rate for f in scaled] == rates
    assert [(f.id, f.src, f.dst, f.cls, f.service) for f in scaled] == \
        [(f.id, f.src, f.dst, f.cls, f.service) for f in FLOWS]


def test_scaling_by_one_is_the_identity():  # S2
    assert scale_flows(FLOWS, 1.0) == FLOWS


def test_scaling_the_template_by_two():  # S4
    traffic = json.loads((FIXTURES / "flows" / "campus.json").read_text())
    flows = resolve_traffic(traffic, resolve_topology(TemplateTopologySpec(template="campus")).topology)
    assert sum(f.rate for f in scale_flows(flows, 2.0)) == 170

