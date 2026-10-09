"""Seeded traffic generator (spec: traffic-generation).

Expected values are the hand-worked numbers confirmed by B (Group 2 of
add-network-generators): G1 to G5, R1 to R4, and the stated properties.
"""

import random
from collections import Counter

import pytest

from core.gen.registry import resolve_topology, resolve_traffic
from core.gen.traffic import access_capacity, class_counts, size_rates, target_demand
from core.model.types import GeneratedTrafficSpec, TemplateTopologySpec

MIX = {0: 0.1, 1: 0.4, 2: 0.5}


def campus():
    return resolve_topology(TemplateTopologySpec(template="campus")).topology


def generate(seed=7, n_flows=200, load_factor=0.5, class_mix=MIX):
    spec = GeneratedTrafficSpec(generator="campus", n_flows=n_flows, load_factor=load_factor,
                                class_mix=class_mix, seed=seed)
    return resolve_traffic(spec, campus())


# Class counts by largest remainder

@pytest.mark.parametrize("n, mix, expected", [
    (200, MIX, {0: 20, 1: 80, 2: 100}),                    # G1
    (17, MIX, {0: 2, 1: 7, 2: 8}),                         # G2
    (10, {0: 0.25, 1: 0.25, 2: 0.5}, {0: 3, 1: 2, 2: 5}),  # G3: tie goes to the lower class
])
def test_class_counts(n, mix, expected):
    counts = class_counts(n, mix)
    assert counts == expected
    assert list(counts) == sorted(counts)


def test_classes_assigned_in_id_order():  # G4
    flows = generate(n_flows=17)
    assert [f.cls for f in flows] == [0] * 2 + [1] * 7 + [2] * 8
    assert [f.id for f in flows] == [f"F{i}" for i in range(1, 18)]


def test_mix_not_summing_to_one_is_rejected():  # G5
    with pytest.raises(ValueError, match="sum"):
        class_counts(10, {0: 0.5, 1: 0.4})


def test_zero_share_gets_no_flows():
    assert class_counts(10, {0: 0.0, 1: 1.0}) == {0: 0, 1: 10}


# Rate sizing

def test_rates_round_half_up():  # R1
    assert size_rates([1, 2, 3, 4], 25) == [3, 5, 8, 10]


def test_rates_have_a_minimum_of_one():  # R2
    assert size_rates([1, 99], 10) == [1, 10]


@pytest.mark.parametrize("load_factor, expected", [(0.5, 85), (0.3, 51)])  # R3, R4
def test_target_demand_on_campus(load_factor, expected):
    assert access_capacity(campus()) == 170
    assert target_demand(campus(), load_factor) == expected


# Properties for any seed

def test_same_seed_same_flows():
    assert generate(seed=1) == generate(seed=1)


def test_different_seeds_differ():
    assert generate(seed=1) != generate(seed=2)


def test_requested_count_unique_ids_and_class_mix():
    flows = generate()
    assert [f.id for f in flows] == [f"F{i}" for i in range(1, 201)]
    assert Counter(f.cls for f in flows) == {0: 20, 1: 80, 2: 100}


def test_rates_and_endpoints_are_valid():
    nodes = {n.id for n in campus().nodes}
    for f in generate():
        assert isinstance(f.rate, int) and f.rate >= 1, f
        assert f.src in nodes and f.dst in nodes and f.src != f.dst, f


def test_p0_flows_target_key_services_with_label():  # task 2.3
    p0 = [f for f in generate() if f.cls == 0]
    assert p0
    for f in p0:
        assert (f.dst, f.service) in {("AUTH", "auth"), ("EMRG", "emergency")}, f


def test_total_is_within_n_of_target():
    flows = generate()
    assert abs(sum(f.rate for f in flows) - 85) <= len(flows)


def test_global_random_state_does_not_matter():
    first = generate(seed=3)
    random.seed(12345)
    random.random()
    assert generate(seed=3) == first


SPEC = GeneratedTrafficSpec(generator="campus", n_flows=5, load_factor=0.5, class_mix=MIX, seed=1)


def test_missing_required_service_is_rejected():
    topo = campus()
    topo = topo.model_copy(update={
        "nodes": [n for n in topo.nodes if n.id != "AUTH"],
        "links": [l for l in topo.links if "AUTH" not in (l.u, l.v)],
    })
    with pytest.raises(ValueError, match="AUTH"):
        resolve_traffic(SPEC, topo)


def test_topology_without_sources_is_rejected():
    diamond = resolve_topology(TemplateTopologySpec(template="diamond")).topology
    with pytest.raises(ValueError, match="building or hostel"):
        resolve_traffic(SPEC, diamond)
