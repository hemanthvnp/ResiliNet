import ast
from pathlib import Path as FsPath

import pytest

from core.routing.pathfinder import (
    connected_components,
    max_flow_value,
    residual_reachable,
    shortest_path,
)


def best_path(arcs, src, dst):
    path = shortest_path(arcs, src, dst)
    assert path is not None
    return path


def both_ways(link_id: str, u: str, v: str, value: int):
    return [(f"{link_id}:{u}>{v}", u, v, value), (f"{link_id}:{v}>{u}", v, u, value)]


def diamond(value_ab=1, value_bd=1, value_ac=2, value_cd=2):
    """PLAN.md section 4: AB, BD, AC, CD. The value is latency or capacity per the caller."""
    return (
        both_ways("L1", "A", "B", value_ab)
        + both_ways("L2", "B", "D", value_bd)
        + both_ways("L3", "A", "C", value_ac)
        + both_ways("L4", "C", "D", value_cd)
    )


# --- shortest_path ---------------------------------------------------------------------


def test_lowest_cost_wins():
    path = best_path(diamond(), "A", "D")
    assert path.nodes == ("A", "B", "D")
    assert path.cost == 2
    assert path.arcs == ("L1:A>B", "L2:B>D")


def test_equal_cost_fewer_hops_wins():
    arcs = [
        ("direct:A>D", "A", "D", 3),
        ("x1:A>B", "A", "B", 1),
        ("x2:B>D", "B", "D", 2),
    ]
    path = best_path(arcs, "A", "D")
    assert path.nodes == ("A", "D")
    assert path.cost == 3


def test_full_tie_node_ids_decide_whatever_the_input_order():
    arcs = diamond(1, 1, 1, 1)
    for ordering in (arcs, list(reversed(arcs))):
        assert best_path(ordering, "A", "D").nodes == ("A", "B", "D")


def test_parallel_links_use_lower_latency_arc():
    arcs = [("L1:A>B", "A", "B", 5), ("L2:A>B", "A", "B", 2)]
    path = best_path(arcs, "A", "B")
    assert path.arcs == ("L2:A>B",)
    assert path.cost == 2


def test_parallel_links_equal_latency_lower_arc_id_wins():
    arcs = [("L2:A>B", "A", "B", 2), ("L1:A>B", "A", "B", 2)]
    assert best_path(arcs, "A", "B").arcs == ("L1:A>B",)


def test_down_link_is_avoided():
    available = [a for a in diamond() if not a[0].startswith("L2:")]  # BD down
    path = best_path(available, "A", "D")
    assert path.nodes == ("A", "C", "D")
    assert path.cost == 4


def test_no_path():
    assert shortest_path(both_ways("L1", "A", "B", 1) + both_ways("L2", "C", "D", 1), "A", "D") is None


def test_unknown_source_has_no_path():
    assert shortest_path(diamond(), "Z", "D") is None


def test_negative_weight_is_rejected():
    with pytest.raises(ValueError):
        shortest_path([("L1:A>B", "A", "B", -1)], "A", "B")


# --- connected_components --------------------------------------------------------------


def test_isolated_node_is_its_own_component():
    nodes = ["A", "B", "C", "D"]
    available = [a for a in diamond() if not a[0].startswith(("L2:", "L4:"))]  # BD, CD down
    assert connected_components(nodes, available) == [("A", "B", "C"), ("D",)]


def test_components_of_healthy_diamond():
    assert connected_components(["D", "C", "B", "A"], diamond()) == [("A", "B", "C", "D")]


# --- residual_reachable ----------------------------------------------------------------


def test_saturated_arc_blocks_reachability():
    arcs = [("L1:A>B", "A", "B", 0), ("L2:B>D", "B", "D", 5)]
    assert residual_reachable(arcs, "A") == frozenset({"A"})


def test_reachability_follows_arc_direction_and_positive_residual():
    arcs = [("L1:A>B", "A", "B", 3), ("L2:B>D", "B", "D", 0), ("L3:C>A", "C", "A", 4)]
    assert residual_reachable(arcs, "A") == frozenset({"A", "B"})


# --- max_flow_value --------------------------------------------------------------------


def test_diamond_max_flow_is_20():
    assert max_flow_value(diamond(10, 10, 10, 10), "A", "D") == 20


def test_max_flow_limited_by_bottleneck():
    arcs = [("L1:A>B", "A", "B", 10), ("L2:B>D", "B", "D", 5)]
    assert max_flow_value(arcs, "A", "D") == 5


def test_max_flow_sums_parallel_arcs():
    arcs = [("L1:A>B", "A", "B", 4), ("L2:A>B", "A", "B", 6)]
    assert max_flow_value(arcs, "A", "B") == 10


def test_max_flow_unknown_node_is_zero():
    assert max_flow_value(diamond(10, 10, 10, 10), "Z", "D") == 0


# --- single wrapper --------------------------------------------------------------------


def test_only_pathfinder_imports_networkx():
    routing = FsPath(__file__).resolve().parents[1]
    for source in routing.glob("*.py"):
        if source.name == "pathfinder.py":
            continue
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            assert not any(n.split(".")[0] == "networkx" for n in names), source.name
