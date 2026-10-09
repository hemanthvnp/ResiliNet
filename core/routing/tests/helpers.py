import json
import random
from pathlib import Path

from core.explain.template import arc_nodes
from core.routing.inputs import AllocConfig, ArcSpec, FlowSpec

EXPECTED = json.loads((Path(__file__).parent / "expected_diamond.json").read_text(encoding="utf-8"))

F1 = FlowSpec("F1", "A", "D", 15, 0)
F2 = FlowSpec("F2", "A", "D", 10, 2)


def link(link_id: str, u: str, v: str, capacity: int, latency: int, up: bool = True) -> list[ArcSpec]:
    return [
        ArcSpec(f"{link_id}:{u}>{v}", u, v, capacity, latency, up),
        ArcSpec(f"{link_id}:{v}>{u}", v, u, capacity, latency, up),
    ]


def diamond(down: tuple[str, ...] = ()) -> list[ArcSpec]:
    """PLAN.md section 4: AB 10/1, BD 10/1, AC 10/2, CD 10/2, each direction."""
    arcs = []
    links = [("L_AB", "A", "B", 1), ("L_BD", "B", "D", 1), ("L_AC", "A", "C", 2), ("L_CD", "C", "D", 2)]
    for link_id, u, v, latency in links:
        arcs += link(link_id, u, v, 10, latency, up=link_id not in down)
    return arcs


def nodes(arcs) -> list[str]:
    """Node sequence of a path given as arc ids."""
    arcs = list(arcs)
    return [arc_nodes(arcs[0])[0]] + [arc_nodes(a)[1] for a in arcs]


def node_paths(outcome) -> list[list[str]]:
    return [nodes(p.arcs) for p in outcome.paths]


def random_case(seed: int):
    """A small random topology (some links down), flows and config, fully determined by `seed`."""
    rng = random.Random(seed)
    names = "ABCDEFG"[: rng.randint(4, 7)]
    arcs: list[ArcSpec] = []
    for i, u in enumerate(names):
        for v in names[i + 1:]:
            if rng.random() < 0.5:
                arcs += link(f"L{u}{v}", u, v, rng.randint(1, 12), rng.randint(1, 5), up=rng.random() > 0.2)
    flows = [
        FlowSpec(f"F{i}", rng.choice(names), rng.choice(names), rng.randint(0, 20), rng.randint(0, 2))
        for i in range(rng.randint(1, 8))
    ]
    cfg = AllocConfig(
        order=rng.choice(["arrival", "class_size_desc", "class_size_asc"]),
        max_paths=rng.randint(1, 4),
        congestion_lambda=rng.randint(0, 5),
        util_cap=rng.choice([1.0, 0.9]),
    )
    return arcs, flows, cfg
