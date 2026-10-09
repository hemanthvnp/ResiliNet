"""Campus template, its traffic, spec resolution and the post-failure path check.

Expected values are the hand-worked numbers confirmed by B (Group 1 of
add-network-generators), from PLAN.md sections 2, 4, 7 and 9.
"""

import json
from collections import Counter
from pathlib import Path

import pytest

from core.gen.campus import CAMPUS_PRIMARY_UPLINK
from core.gen.registry import resolve_topology, resolve_traffic
from core.model.types import Flow, TemplateTopologySpec, Topology

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"

LINKS = {
    "L1": ("C1", "C2", 100, 1),
    "L2": ("C1", "AUTH", 100, 1),
    "L3": ("C1", "EMRG", 100, 1),
    "L4": ("C1", "LMS", 100, 1),
    "L5": ("C1", "INET", 100, 1),
    "L6": ("D1", "C1", 50, 1),
    "L7": ("D1", "C2", 20, 1),
    "L8": ("D2", "C1", 50, 1),
    "L9": ("D2", "C2", 20, 1),
    "L10": ("B1", "D1", 20, 1),
    "L11": ("B1", "D2", 10, 3),
    "L12": ("B2", "D1", 20, 1),
    "L13": ("B2", "D2", 10, 3),
    "L14": ("B3", "D1", 20, 1),
    "L15": ("B3", "D2", 10, 3),
    "L16": ("B4", "D2", 20, 1),
    "L17": ("B4", "D1", 10, 3),
    "L18": ("B5", "D2", 20, 1),
    "L19": ("B5", "D1", 10, 3),
    "L20": ("H1", "D2", 10, 1),
    "L21": ("H2", "D2", 10, 1),
}

NODE_TYPES = {
    "C1": "core", "C2": "core",
    "AUTH": "service", "EMRG": "service", "LMS": "service", "INET": "service",
    "D1": "distribution", "D2": "distribution",
    "B1": "building", "B2": "building", "B3": "building", "B4": "building", "B5": "building",
    "H1": "hostel", "H2": "hostel",
}


def campus():
    return resolve_topology(TemplateTopologySpec(template="campus"))


def campus_flows():
    return resolve_traffic(json.loads((FIXTURES / "flows" / "campus.json").read_text()), campus().topology)


# 1a: topology

def test_template_nodes():
    topo = campus().topology
    assert {n.id: n.type for n in topo.nodes} == NODE_TYPES
    assert len(topo.nodes) == 15
    names = {n.id: n.name for n in topo.nodes}
    assert (names["H1"], names["H2"]) == ("Boys' hostel", "Girls' hostel")


def test_template_links():
    topo = campus().topology
    assert {l.id: (l.u, l.v, l.capacity, l.latency) for l in topo.links} == LINKS
    assert all(l.status == "up" for l in topo.links)


def test_primary_uplink_is_d1_to_c1():
    resolved = campus()
    assert resolved.primary_uplink == CAMPUS_PRIMARY_UPLINK == "L6"
    assert LINKS["L6"] == ("D1", "C1", 50, 1)


def test_template_loads_identically_twice():
    assert campus().topology.model_dump_json() == campus().topology.model_dump_json()


def test_unknown_template_raises_with_its_name():
    with pytest.raises(KeyError, match="nowhere"):
        resolve_topology(TemplateTopologySpec(template="nowhere"))


# 1b: traffic

FLOWS = (
    [(f"F{3 * i + 1}", b, "AUTH", 2, 0, "auth") for i, b in enumerate(["B1", "B2", "B3", "B4", "B5"])]
    + [(f"F{3 * i + 2}", b, "LMS", 8, 1, "lms") for i, b in enumerate(["B1", "B2", "B3", "B4", "B5"])]
    + [(f"F{3 * i + 3}", b, "INET", 5, 2, "internet") for i, b in enumerate(["B1", "B2", "B3", "B4", "B5"])]
    + [("F16", "H1", "EMRG", 1, 0, "emergency"), ("F17", "H1", "INET", 4, 2, "internet")]
    + [("F18", "H2", "EMRG", 1, 0, "emergency"), ("F19", "H2", "INET", 4, 2, "internet")]
)


def test_template_traffic():
    flows = campus_flows()
    assert sorted((f.id, f.src, f.dst, f.rate, f.cls, f.service) for f in flows) == sorted(FLOWS)
    assert [f.id for f in flows] == [f"F{i}" for i in range(1, 20)]


def test_template_traffic_totals_and_load_factor():
    flows = campus_flows()
    assert sum(f.rate for f in flows) == 85
    by_class = Counter()
    for f in flows:
        by_class[f.cls] += f.rate
    assert dict(by_class) == {0: 12, 1: 40, 2: 33}
    assert Counter(f.cls for f in flows) == {0: 7, 1: 5, 2: 7}
    types = {n.id: n.type for n in campus().topology.nodes}
    access = sum(l.capacity for l in campus().topology.links
                 if types[l.u] in ("building", "hostel") or types[l.v] in ("building", "hostel"))
    assert access == 170
    assert 85 / access == 0.5


def test_explicit_traffic_passes_through_unchanged():
    raw = json.loads((FIXTURES / "flows" / "diamond.json").read_text())
    diamond = Topology.model_validate_json((FIXTURES / "topologies" / "diamond.json").read_bytes())
    assert resolve_traffic(raw, diamond) == [Flow(**f) for f in raw]


def test_explicit_traffic_with_unknown_node_is_rejected():
    with pytest.raises(ValueError, match="Z"):
        resolve_traffic([{"id": "F1", "src": "A", "dst": "Z", "rate": 1, "cls": 0}], campus().topology)
