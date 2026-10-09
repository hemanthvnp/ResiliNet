"""Seeded traffic generator (PLAN.md sections 2, 7 and 9).

Classes are assigned exactly: largest-remainder counts from `class_mix`, given to
flows in id order. Each flow then draws, from one random.Random(seed) and in a fixed
order, a source (a building or hostel), a destination for its class, and a weight
from 1 to 10. Weights are scaled so the total is about load_factor times the access
capacity, rounding half up with a minimum of 1. All arithmetic on the float inputs
is exact (Fraction of their decimal form).
"""

from __future__ import annotations

import math
import random
from fractions import Fraction

from core.model.types import Flow, GeneratedTrafficSpec, Topology

SOURCE_TYPES = ("building", "hostel")
# class -> destination node ids; P0 goes to the key services (PLAN.md section 2)
DESTINATIONS = {0: ("AUTH", "EMRG"), 1: ("LMS",), 2: ("INET",)}
SERVICE_LABELS = {"AUTH": "auth", "EMRG": "emergency", "LMS": "lms", "INET": "internet"}
WEIGHT_RANGE = (1, 10)


def _exact(x: float) -> Fraction:
    return Fraction(repr(x))


def _half_up(x: Fraction) -> int:
    return math.floor(x + Fraction(1, 2))


def class_counts(n: int, mix: dict[int, float]) -> dict[int, int]:
    """Largest-remainder split of n flows by share; ties go to the lower class.
    Shares must be non-negative and sum to exactly 1."""
    shares = {cls: _exact(mix[cls]) for cls in sorted(mix)}
    if any(s < 0 for s in shares.values()) or sum(shares.values()) != 1:
        raise ValueError(f"class_mix shares must be non-negative and sum to 1, got {mix}")
    quotas = {cls: n * s for cls, s in shares.items()}
    counts = {cls: math.floor(q) for cls, q in quotas.items()}
    left = n - sum(counts.values())
    by_remainder = sorted(quotas, key=lambda cls: (-(quotas[cls] - counts[cls]), cls))
    for cls in by_remainder[:left]:
        counts[cls] += 1
    return counts


def size_rates(weights: list[int], target: int) -> list[int]:
    """Each weight's share of `target`, rounded half up, at least 1."""
    total = sum(weights)
    return [max(1, _half_up(Fraction(w * target, total))) for w in weights]


def access_capacity(topo: Topology) -> int:
    """Sum of capacities of links touching a building or hostel."""
    types = {n.id: n.type for n in topo.nodes}
    return sum(l.capacity for l in topo.links
               if types[l.u] in SOURCE_TYPES or types[l.v] in SOURCE_TYPES)


def target_demand(topo: Topology, load_factor: float) -> int:
    return _half_up(_exact(load_factor) * access_capacity(topo))


def generate_traffic(spec: GeneratedTrafficSpec, topo: Topology) -> list[Flow]:
    nodes = {n.id for n in topo.nodes}
    sources = sorted(n.id for n in topo.nodes if n.type in SOURCE_TYPES)
    if not sources:
        raise ValueError("topology has no building or hostel nodes to send traffic from")
    counts = class_counts(spec.n_flows, spec.class_mix)
    for cls, count in counts.items():
        if count and cls not in DESTINATIONS:
            raise ValueError(f"no destinations defined for class {cls}")
        missing = [d for d in DESTINATIONS.get(cls, ()) if d not in nodes]
        if count and missing:
            raise ValueError(f"class {cls} needs service node(s) {', '.join(missing)}")

    rng = random.Random(spec.seed)
    drawn = []  # (cls, src, dst, weight), in flow id order
    for cls, count in counts.items():
        for _ in range(count):
            src = rng.choice(sources)
            dst = rng.choice(DESTINATIONS[cls])
            weight = rng.randint(*WEIGHT_RANGE)
            drawn.append((cls, src, dst, weight))

    rates = size_rates([w for *_, w in drawn], target_demand(topo, spec.load_factor)) if drawn else []
    return [
        Flow(id=f"F{i}", src=src, dst=dst, rate=rate, cls=cls, service=SERVICE_LABELS[dst])
        for i, ((cls, src, dst, _), rate) in enumerate(zip(drawn, rates), start=1)
    ]
