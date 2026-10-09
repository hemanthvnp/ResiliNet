import pytest

pytest.importorskip("scipy")

from core.model.types import PolicyConfig  # noqa: E402
from core.routing.allocator import allocate  # noqa: E402
from core.routing.lp_reference import lp_upper_bound  # noqa: E402
from core.routing.tests.helpers import (  # noqa: E402
    CASES,
    F1,
    F2,
    blocking_flow,
    blocking_links,
    diamond,
    flow,
    random_case,
    random_network,
    run,
    topology,
)

TOLERANCE = 1e-6


def delivered(result, flows, cls=None):
    return sum(result.outcomes[f.id].delivered for f in flows if cls is None or f.cls == cls)


# Hand-worked. The cut {AB, AC} (or {BD, CD}) has capacity 20, so no more than 20 can reach D,
# and F1 + F2 = 25 asks for more: total 20. F1 alone is capped by its demand of 15 and F2 alone
# by its demand of 10, since 20 of capacity covers either.
def test_healthy_diamond_bound():
    bound = lp_upper_bound(topology(diamond()), [F1, F2])
    assert bound.total == pytest.approx(20, abs=TOLERANCE)
    assert bound.by_class == pytest.approx({0: 15, 2: 10}, abs=TOLERANCE)


# With BD down only A-C-D is left, capacity 10: total 10, and each class alone gets at most 10.
def test_bd_failed_diamond_bound():
    bound = lp_upper_bound(topology(diamond(down=("L_BD",))), [F1, F2])
    assert bound.total == pytest.approx(10, abs=TOLERANCE)
    assert bound.by_class == pytest.approx({0: 10, 2: 10}, abs=TOLERANCE)


@pytest.mark.parametrize("down", [(), ("L_BD",)])
def test_never_below_s2_on_the_diamond(down):
    topo = topology(diamond(down))
    s2 = run(allocate, topo, [F1, F2], PolicyConfig())
    bound = lp_upper_bound(topo, [F1, F2])
    assert bound.total >= delivered(s2, [F1, F2]) - TOLERANCE
    for cls in (0, 2):
        assert bound.by_class[cls] >= delivered(s2, [F1, F2], cls) - TOLERANCE


def test_blocking_example_shows_the_greedy_gap():
    # Max flow is 3 (the cut L1 + L2 + L3); the greedy delivers 2.
    flows = [blocking_flow()]
    topo = topology(blocking_links())
    bound = lp_upper_bound(topo, flows)
    s2 = run(allocate, topo, flows, PolicyConfig())
    assert bound.total == pytest.approx(CASES["blocking"]["maxflow"], abs=TOLERANCE)
    assert delivered(s2, flows) == CASES["blocking"]["delivered"]


def test_util_cap_lowers_the_bound():
    # A to B in the diamond: the direct link (10) and A-C-D-B (10, via 2 + 2 + 1) give 20 at
    # util_cap 1 and 2 * floor(0.9 * 10) = 18 at 0.9.
    topo = topology(diamond())
    flows = [flow("X", "A", "B", 20, 0)]
    assert lp_upper_bound(topo, flows, 1.0).total == pytest.approx(20, abs=TOLERANCE)
    assert lp_upper_bound(topo, flows, 0.9).total == pytest.approx(18, abs=TOLERANCE)


def test_disconnected_zero_rate_and_same_endpoint_flows():
    flows = [flow("a", "A", "Z", 5, 0), flow("b", "A", "D", 0, 0), flow("c", "A", "A", 7, 1)]
    bound = lp_upper_bound(topology(diamond(), extra_nodes=["Z"]), flows)
    assert bound.total == pytest.approx(7, abs=TOLERANCE)
    assert bound.by_class == pytest.approx({0: 0, 1: 7}, abs=TOLERANCE)


def test_no_routable_flows():
    bound = lp_upper_bound(topology(diamond()), [flow("c", "A", "A", 7, 1)])
    assert bound.total == 7 and bound.by_class == {1: 7.0}


@pytest.mark.parametrize("seed", range(40))
def test_never_below_s2_on_random_inputs(seed):
    topo, flows, cfg = random_case(seed)
    cfg = cfg.model_copy(update={"order": "class_size_desc"})
    s2 = run(allocate, topo, flows, cfg)
    bound = lp_upper_bound(topo, flows, cfg.util_cap)
    context = f"seed={seed} cfg={cfg}"
    assert bound.total >= delivered(s2, flows) - TOLERANCE, context
    for cls, value in bound.by_class.items():
        assert value >= delivered(s2, flows, cls) - TOLERANCE, context


@pytest.mark.parametrize("seed", range(3))
def test_never_below_s2_at_25_nodes(seed):
    topo, flows = random_network(seed)
    s2 = run(allocate, topo, flows, PolicyConfig())
    bound = lp_upper_bound(topo, flows)
    assert bound.total >= delivered(s2, flows) - TOLERANCE, f"seed={seed}"
    assert bound.total <= sum(f.rate for f in flows) + TOLERANCE


@pytest.mark.parametrize("seed", range(20))
def test_single_flow_equals_min_of_rate_and_max_flow(seed):
    # Independent cross-check of the LP against the max-flow code in the pathfinder.
    from core.model.arcs import available_arcs
    from core.routing.pathfinder import max_flow_value

    topo, flows = random_network(seed, nodes=12, extra_links=12, flows=1)
    f = flows[0]
    tuples = [(a.id, a.src, a.dst, a.capacity) for a in available_arcs(topo)]
    expected = min(f.rate, max_flow_value(tuples, f.src, f.dst))
    assert lp_upper_bound(topo, flows).total == pytest.approx(expected, abs=TOLERANCE), f"seed={seed}"
