"""Campus network: the hand-drawn template's metadata and the seeded generator.

The template itself is the fixture fixtures/topologies/campus.json, tuned by hand
(PLAN.md sections 9 and 12). The frozen Topology has no field for the primary
uplink, so its id lives here, next to the loader that knows which fixture it belongs to.
Node roles are carried in Node.type: core, distribution, building, hostel, service.

The generator mirrors the template's three tiers. Every building has a primary and
a secondary uplink to two different distribution nodes, so the post-failure path
check can pass; `redundancy` is the probability of a third uplink, straight to a
core node. Ids come from counters in creation order (cores, distribution, buildings,
hostels), except the services, which keep the fixed ids the traffic generator targets.
All draws go through one random.Random(seed) in a fixed order.
"""

from __future__ import annotations

import math
import random

from core.gen.resolved import ResolvedTopology
from core.model.types import GeneratedTopologySpec, GeneratedTrafficSpec, Link, Node, Topology

CAMPUS_PRIMARY_UPLINK = "L6"  # first distribution node to first core; scenario 2 and the path check

SERVICES = [("AUTH", "Auth server"), ("EMRG", "Emergency"), ("LMS", "Learning platform"),
            ("INET", "Internet gateway")]
HOSTELS = 2
BUILDINGS_PER_DISTRIBUTION = 8

# (capacity, latency) per link role
CORE_LINK = (1000, 1)
SERVICE_LINK = (1000, 1)
PRIMARY_ACCESS = (20, 1)
SECONDARY_ACCESS = (10, 3)
EXTRA_TO_CORE = (10, 2)
HOSTEL_ACCESS = (10, 1)
UPLINK_LATENCY = 1

DEFAULT_TOPOLOGY = GeneratedTopologySpec(generator="campus", buildings=37, redundancy=0.5, seed=1)
DEFAULT_TRAFFIC = GeneratedTrafficSpec(generator="campus", n_flows=200, load_factor=0.5,
                                       class_mix={0: 0.1, 1: 0.4, 2: 0.5}, seed=1)


def distribution_count(buildings: int) -> int:
    return max(2, math.ceil(buildings / BUILDINGS_PER_DISTRIBUTION))


def uplink_capacities(primaries: int, hostels: int) -> tuple[int, int]:
    """(to first core, to second core) for a distribution node."""
    first = max(20, PRIMARY_ACCESS[0] * primaries + HOSTEL_ACCESS[0] * hostels)
    return first, max(10, math.ceil(first / 2))


def generate_campus(spec: GeneratedTopologySpec) -> ResolvedTopology:
    if spec.buildings < 1:
        raise ValueError(f"buildings must be at least 1, got {spec.buildings}")
    if not 0 <= spec.redundancy <= 1:
        raise ValueError(f"redundancy must be in [0, 1], got {spec.redundancy}")
    rng = random.Random(spec.seed)

    counter = iter(range(1, 10**9))
    cores = [f"N{next(counter)}" for _ in range(2)]
    dists = [f"N{next(counter)}" for _ in range(distribution_count(spec.buildings))]
    buildings = [f"N{next(counter)}" for _ in range(spec.buildings)]
    hostels = [f"N{next(counter)}" for _ in range(HOSTELS)]

    # Draws, in a fixed order: per building primary, secondary, coin, core; then per hostel.
    access = []  # (building, distribution or core, (capacity, latency))
    primaries = {d: 0 for d in dists}
    for b in buildings:
        primary = rng.choice(dists)
        secondary = rng.choice([d for d in dists if d != primary])
        access += [(b, primary, PRIMARY_ACCESS), (b, secondary, SECONDARY_ACCESS)]
        primaries[primary] += 1
        if rng.random() < spec.redundancy:
            access.append((b, rng.choice(cores), EXTRA_TO_CORE))
    hostel_on = {h: rng.choice(dists) for h in hostels}

    nodes = (
        [Node(id=c, type="core", name=f"Core {i}") for i, c in enumerate(cores, 1)]
        + [Node(id=sid, type="service", name=name) for sid, name in SERVICES]
        + [Node(id=d, type="distribution", name=f"Distribution {i}") for i, d in enumerate(dists, 1)]
        + [Node(id=b, type="building", name=f"Building {i}") for i, b in enumerate(buildings, 1)]
        + [Node(id=h, type="hostel", name=f"Hostel {i}") for i, h in enumerate(hostels, 1)]
    )

    ends = [(cores[0], cores[1], CORE_LINK)]
    ends += [(cores[0], sid, SERVICE_LINK) for sid, _ in SERVICES]
    for d in dists:
        to_first, to_second = uplink_capacities(primaries[d], sum(1 for h in hostels if hostel_on[h] == d))
        ends += [(d, cores[0], (to_first, UPLINK_LATENCY)), (d, cores[1], (to_second, UPLINK_LATENCY))]
    ends += access
    ends += [(h, hostel_on[h], HOSTEL_ACCESS) for h in hostels]

    links = [Link(id=f"L{i}", u=u, v=v, capacity=cap, latency=lat, status="up")
             for i, (u, v, (cap, lat)) in enumerate(ends, 1)]
    return ResolvedTopology(Topology(nodes=nodes, links=links), CAMPUS_PRIMARY_UPLINK, spec.seed)
