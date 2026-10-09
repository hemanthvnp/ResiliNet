"""Per-seed benchmark cases (change add-cli-benchmark, task 3.1; design: "Stress cases are generated per seed").

For each seed one campus network and one flow list are resolved through B's generators, then
four cases differ only in their events:

    healthy    no event                                   like fixture scenario 1
    uplink     fail the primary uplink                    like scenario 2
    multi      fail three random links in one event       like scenario 3
    recovered  fail three random links, then recover them like scenario 8

Failure sets never depend on a policy. Each random purpose has its own random.Random, seeded
by arithmetic on the benchmark seed (seed * 1000 + purpose), never hash(), and draws over the
link ids sorted first, so adding a purpose never shifts another's draws.
"""

from __future__ import annotations

import random

from core.gen.campus import DEFAULT_TOPOLOGY, DEFAULT_TRAFFIC
from core.gen.registry import resolve_inputs
from core.model.types import (
    Event,
    GeneratedTopologySpec,
    GeneratedTrafficSpec,
    PolicyConfig,
    Scenario,
    Topology,
)

CASES = ("healthy", "uplink", "multi", "recovered")
RANDOM_FAILURES = 3

# Purpose numbers of the derived RNGs. Never renumber one: that changes every past draw.
PURPOSE_MULTI = 1
PURPOSE_RECOVERED = 2


def purpose_rng(seed: int, purpose: int) -> random.Random:
    return random.Random(seed * 1000 + purpose)


def draw_links(topology: Topology, seed: int, purpose: int, k: int = RANDOM_FAILURES) -> list[str]:
    ids = sorted(l.id for l in topology.links)
    return sorted(purpose_rng(seed, purpose).sample(ids, k))


def build_cases(seed: int, topology_spec: GeneratedTopologySpec = DEFAULT_TOPOLOGY,
                traffic_spec: GeneratedTrafficSpec = DEFAULT_TRAFFIC) -> list[Scenario]:
    """The four cases of one seed, in CASES order. Every case carries the same topology spec
    (with the seed the generator actually used) and the same explicit flow list. The two specs
    give the size; the default is the demo size (about 50 nodes and 200 flows)."""
    resolved, flows = resolve_inputs(topology_spec.model_copy(update={"seed": seed}),
                                     traffic_spec.model_copy(update={"seed": seed}))
    topology = resolved.topology
    multi = draw_links(topology, seed, PURPOSE_MULTI)
    recovered = draw_links(topology, seed, PURPOSE_RECOVERED)
    events = {
        "healthy": [],
        "uplink": [Event(step=1, kind="fail", links=[resolved.primary_uplink])],
        "multi": [Event(step=1, kind="fail", links=multi)],
        "recovered": [Event(step=1, kind="fail", links=recovered),
                      Event(step=2, kind="recover", links=recovered)],
    }
    spec = topology_spec.model_copy(update={"seed": resolved.seed})
    return [
        Scenario(id=f"seed{seed}-{case}", seed=seed, topology=spec, traffic=flows,
                 events=events[case], config=PolicyConfig())
        for case in CASES
    ]
