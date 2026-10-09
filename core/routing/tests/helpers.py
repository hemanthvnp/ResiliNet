import json
import random
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from core.explain.template import arc_nodes
from core.model.types import Allocation, DecisionRecord, Flow, FlowResult, Link, Node, PolicyConfig, Topology

EXPECTED = json.loads((Path(__file__).parent / "expected_diamond.json").read_text(encoding="utf-8"))
CASES = json.loads((Path(__file__).parent / "expected_cases.json").read_text(encoding="utf-8"))
RECORDS = json.loads(
    (Path(__file__).parents[2] / "explain" / "tests" / "expected_records.json").read_text(encoding="utf-8")
)

F1 = Flow(id="F1", src="A", dst="D", rate=15, cls=0)
F2 = Flow(id="F2", src="A", dst="D", rate=10, cls=2)


def flow(flow_id: str, src: str, dst: str, rate: int, cls: int) -> Flow:
    return Flow(id=flow_id, src=src, dst=dst, rate=rate, cls=cls)


def loaded(arc_load: dict[str, int]) -> dict[str, int]:
    """The arcs of an arc_load that carry something (the contract lists every available arc)."""
    return {arc: value for arc, value in arc_load.items() if value}


def link(link_id: str, u: str, v: str, capacity: int, latency: int, up: bool = True) -> list[Link]:
    """One link, as a list so that tests can add lists of links together."""
    return [Link(id=link_id, u=u, v=v, capacity=capacity, latency=latency, status="up" if up else "down")]


def topology(links: Iterable[Link], extra_nodes: Iterable[str] = ()) -> Topology:
    links = list(links)
    names = sorted({n for lk in links for n in (lk.u, lk.v)} | set(extra_nodes))
    return Topology(nodes=[Node(id=n, type="router", name=n) for n in names], links=links)


def diamond(down: tuple[str, ...] = ()) -> list[Link]:
    """PLAN.md section 4: AB 10/1, BD 10/1, AC 10/2, CD 10/2 (capacity/latency)."""
    links: list[Link] = []
    spec = [("L_AB", "A", "B", 1), ("L_BD", "B", "D", 1), ("L_AC", "A", "C", 2), ("L_CD", "C", "D", 2)]
    for link_id, u, v, latency in spec:
        links += link(link_id, u, v, 10, latency, up=link_id not in down)
    return links


@dataclass
class Run:
    """What a policy returned, with the names the tests use."""

    allocation: Allocation
    records: list[DecisionRecord]

    @property
    def outcomes(self) -> dict[str, FlowResult]:
        return self.allocation.results

    @property
    def arc_load(self) -> dict[str, int]:
        return self.allocation.arc_load


def run(
    policy: Callable,
    links: Topology | Iterable[Link],
    flows: Sequence[Flow],
    cfg: PolicyConfig | None = None,
    prev: Allocation | None = None,
    **kwargs,
) -> Run:
    """Call a policy function (topo, flows, prev, cfg, ...) and wrap what it returns."""
    topo = links if isinstance(links, Topology) else topology(links)
    allocation, records = policy(topo, flows, prev, cfg or PolicyConfig(), **kwargs)
    return Run(allocation, records)


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
    links: list[Link] = []
    for i, u in enumerate(names):
        for v in names[i + 1:]:
            if rng.random() < 0.5:
                links += link(f"L{u}{v}", u, v, rng.randint(1, 12), rng.randint(1, 5), up=rng.random() > 0.2)
    flows = [
        Flow(id=f"F{i}", src=rng.choice(names), dst=rng.choice(names), rate=rng.randint(0, 20), cls=rng.randint(0, 2))
        for i in range(rng.randint(1, 8))
    ]
    cfg = PolicyConfig(
        order=rng.choice(["arrival", "class_size_desc", "class_size_asc"]),
        max_paths=rng.randint(1, 4),
        congestion_lambda=rng.randint(0, 5),
        util_cap=rng.choice([1.0, 0.9]),
    )
    return topology(links, extra_nodes=names), flows, cfg


def blocking_links() -> list[Link]:
    return [
        Link(id=i, u=u, v=v, capacity=cap, latency=lat, status="up") for i, u, v, cap, lat in CASES["blocking"]["links"]
    ]


def blocking_flow() -> Flow:
    return Flow(**CASES["blocking"]["flow"])


def cut_view(record) -> list[dict]:
    """The cut of a record in the JSON shape of expected_records.json."""
    return [
        {"arc": c.arc, "state": c.state, "load_by_class": {str(k): v for k, v in c.load_by_class.items()}}
        for c in record.cut
    ]


def random_network(seed: int, nodes: int = 25, extra_links: int = 35, flows: int = 60):
    """A connected random network with capacities 10/40/100 and flows of mixed class."""
    rng = random.Random(seed)
    names = [f"N{i:02d}" for i in range(nodes)]
    edges: set[tuple[str, str]] = set()
    for i in range(1, nodes):  # a random tree keeps the network connected
        edges.add((names[rng.randrange(i)], names[i]))
    while len(edges) < nodes - 1 + extra_links:
        u, v = rng.sample(names, 2)
        if (u, v) not in edges and (v, u) not in edges:
            edges.add((u, v))
    links: list[Link] = []
    for k, (u, v) in enumerate(sorted(edges)):
        links += link(f"L{k}", u, v, rng.choice([10, 40, 100]), rng.randint(1, 10))
    demands = []
    for i in range(flows):
        src, dst = rng.sample(names, 2)
        demands.append(
            Flow(id=f"F{i:03d}", src=src, dst=dst, rate=rng.randint(1, 60), cls=rng.choices([0, 1, 2], [1, 3, 6])[0])
        )
    return topology(links), demands
