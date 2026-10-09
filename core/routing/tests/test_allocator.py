import pytest

from core.model.arcs import available_arcs
from core.model.ledger import effective_capacity
from core.model.types import Allocation, FlowResult, PathAlloc, PolicyConfig
from core.routing.allocator import allocate
from core.routing.tests.helpers import (
    CASES,
    EXPECTED,
    F1,
    F2,
    blocking_flow,
    blocking_links,
    diamond,
    flow,
    link,
    loaded,
    node_paths,
    nodes,
    random_case,
    run,
)

S2 = PolicyConfig(order="class_size_desc", max_paths=3, congestion_lambda=0, util_cap=1.0)


def rates(outcome):
    return [p.rate for p in outcome.paths]


# --- the diamond, both rows (expected_diamond.json) -------------------------------------


@pytest.mark.parametrize("case, down", [("healthy", ()), ("bd_failed", ("L_BD",))])
def test_s2_matches_expected_table(case, down):
    expected = EXPECTED["cases"][case]["S2"]
    result = run(allocate, diamond(down), [F1, F2], S2)
    for flow_id in ("F1", "F2"):
        outcome = result.outcomes[flow_id]
        assert node_paths(outcome) == expected["paths"][flow_id]
        assert rates(outcome) == expected["rates"][flow_id]
        assert outcome.delivered == expected["delivered"][flow_id]
        assert outcome.unserved == expected["unserved"][flow_id]
        assert outcome.cause == expected["cause"][flow_id]


def test_healthy_diamond_loads_are_within_capacity():
    result = run(allocate, diamond(), [F1, F2], S2)
    assert loaded(result.arc_load) == {"L_AB:A>B": 10, "L_AC:A>C": 10, "L_BD:B>D": 10, "L_CD:C>D": 10}


def test_arc_load_lists_every_available_arc_and_no_down_arc():
    # The frozen fixtures list zero-load arcs too; the arcs of a down link are left out.
    result = run(allocate, diamond(down=("L_BD",)), [F1], S2)
    assert sorted(result.arc_load) == ["L_AB:A>B", "L_AB:B>A", "L_AC:A>C", "L_AC:C>A", "L_CD:C>D", "L_CD:D>C"]
    assert loaded(result.arc_load) == {"L_AC:A>C": 10, "L_CD:C>D": 10}


def test_path_limit_case_matches_expected_cases():
    expected = CASES["path_limit"]
    result = run(allocate, diamond(), [F1], PolicyConfig(max_paths=expected["max_paths"]))
    outcome = result.outcomes["F1"]
    assert node_paths(outcome) == expected["paths"] and rates(outcome) == expected["rates"]
    assert (outcome.delivered, outcome.unserved, outcome.cause) == (
        expected["delivered"],
        expected["unserved"],
        expected["cause"],
    )


# --- hard constraints ----------------------------------------------------------------------


def test_util_cap_case_matches_expected_cases():
    expected = CASES["util_cap"]
    links = link("L1", "A", "B", expected["capacity"], 1)
    cfg = PolicyConfig(util_cap=expected["util_cap"])
    result = run(allocate, links, [flow("X", "A", "B", expected["rate"], 0)], cfg)
    outcome = result.outcomes["X"]
    assert (outcome.delivered, outcome.unserved, outcome.cause) == (
        expected["delivered"],
        expected["unserved"],
        expected["cause"],
    )
    assert loaded(result.arc_load) == expected["arc_load"]


def test_util_cap_rounding_is_exact():
    # floor(0.29 * 100) is 29 (the float product is 28.999999999999996).
    result = run(allocate, link("L1", "A", "B", 100, 1), [flow("X", "A", "B", 100, 0)], PolicyConfig(util_cap=0.29))
    assert result.outcomes["X"].delivered == 29


@pytest.mark.parametrize("seed", range(60))
def test_hard_constraints_hold_on_random_inputs(seed):
    topo, flows, cfg = random_case(seed)
    by_id = {a.id: a for a in available_arcs(topo)}
    result = run(allocate, topo, flows, cfg)
    context = f"seed={seed} cfg={cfg}"
    load: dict[str, int] = {}
    for f in flows:
        outcome = result.outcomes[f.id]
        assert len(outcome.paths) <= cfg.max_paths, context
        assert outcome.delivered + outcome.unserved == f.rate, context
        assert sum(p.rate for p in outcome.paths) == outcome.delivered or f.src == f.dst, context
        for p in outcome.paths:
            assert all(a in by_id for a in p.arcs), context  # only available arcs
            walk = nodes(p.arcs)
            assert walk[0] == f.src and walk[-1] == f.dst and len(set(walk)) == len(walk), context
            for a in p.arcs:
                load[a] = load.get(a, 0) + p.rate
    for arc_id, value in load.items():
        assert value <= effective_capacity(by_id[arc_id].capacity, cfg.util_cap), context
    assert loaded(result.arc_load) == dict(sorted(load.items())), context
    assert sorted(result.arc_load) == sorted(by_id), context
    assert len(result.records) == len(flows), context


@pytest.mark.parametrize("seed", range(30))
def test_removing_lower_classes_changes_nothing_above(seed):
    topo, flows, cfg = random_case(seed)
    cfg = cfg.model_copy(update={"order": "class_size_desc"})
    full = run(allocate, topo, flows, cfg)
    for cutoff in (0, 1):  # drop every class above `cutoff`
        kept = [f for f in flows if f.cls <= cutoff]
        reduced = run(allocate, topo, kept, cfg)
        for f in kept:
            assert reduced.outcomes[f.id].paths == full.outcomes[f.id].paths, f"seed={seed} cutoff={cutoff}"


# --- ordering and cost ------------------------------------------------------------------


def test_class_order_places_critical_flow_first():
    # One arc of capacity 10; the P2 flow comes first in the input but P0 is placed first.
    flows = [flow("low", "A", "B", 10, 2), flow("crit", "A", "B", 10, 0)]
    result = run(allocate, link("L1", "A", "B", 10, 1), flows, S2)
    assert result.outcomes["crit"].delivered == 10 and result.outcomes["low"].delivered == 0
    assert list(result.outcomes) == ["crit", "low"]


def test_arrival_order_ignores_class():
    flows = [flow("low", "A", "B", 10, 2), flow("crit", "A", "B", 10, 0)]
    result = run(allocate, link("L1", "A", "B", 10, 1), flows, PolicyConfig(order="arrival"))
    assert result.outcomes["low"].delivered == 10 and result.outcomes["crit"].delivered == 0


def congestion_case(congestion_lambda):
    # G1 (9 Mbps) takes A-B-D. G2 (5 Mbps) then sees A-B-D at 90% utilization.
    flows = [flow("G1", "A", "D", 9, 0), flow("G2", "A", "D", 5, 0)]
    return run(allocate, diamond(), flows, PolicyConfig(max_paths=3, congestion_lambda=congestion_lambda))


def test_lambda_zero_ignores_congestion():
    # Pure latency: G2 pushes the 1 Mbps left on A-B-D, then 4 on A-C-D.
    g2 = congestion_case(0).outcomes["G2"]
    assert node_paths(g2) == [["A", "B", "D"], ["A", "C", "D"]] and rates(g2) == [1, 4]


def test_nearly_full_route_is_avoided_when_lambda_positive():
    # Slope 70 at 0.9: A-B-D costs (1 + 69) + (1 + 69) = 140 against 4 for A-C-D.
    g2 = congestion_case(1).outcomes["G2"]
    assert node_paths(g2) == [["A", "C", "D"]] and rates(g2) == [5]
    assert g2.paths[0].rate == 5 and g2.delivered == 5


# --- causes and degenerate flows ----------------------------------------------------------


def test_disconnected_destination():
    result = run(allocate, diamond(down=("L_AB", "L_AC")), [F1], S2)
    outcome = result.outcomes["F1"]
    assert (outcome.paths, outcome.delivered, outcome.unserved, outcome.cause) == ([], 0.0, 15.0, "DISCONNECTED")
    assert result.records[0].attempts == []  # no path search was attempted


def test_unknown_destination_is_disconnected():
    outcome = run(allocate, diamond(), [flow("X", "A", "Z", 5, 0)], S2).outcomes["X"]
    assert outcome.cause == "DISCONNECTED"


def test_blocking_example_matches_expected_cases():
    expected = CASES["blocking"]
    outcome = run(allocate, blocking_links(), [blocking_flow()], S2).outcomes["X"]
    assert node_paths(outcome) == expected["paths"] and rates(outcome) == expected["rates"]
    assert (outcome.delivered, outcome.unserved, outcome.cause) == (
        expected["delivered"],
        expected["unserved"],
        expected["cause"],
    )


def test_same_source_and_destination_is_delivered_without_load():
    result = run(allocate, diamond(), [flow("X", "A", "A", 7, 0)], S2)
    outcome = result.outcomes["X"]
    assert (outcome.paths, outcome.delivered, outcome.unserved, outcome.cause) == ([], 7.0, 0.0, "NONE")
    assert loaded(result.arc_load) == {}


def test_zero_rate_flow():
    outcome = run(allocate, diamond(), [flow("X", "A", "D", 0, 0)], S2).outcomes["X"]
    assert (outcome.paths, outcome.delivered, outcome.unserved, outcome.cause) == ([], 0.0, 0.0, "NONE")


# --- purity ------------------------------------------------------------------------------


def previous(paths_by_flow: dict[str, list[PathAlloc]]) -> Allocation:
    results = {
        fid: FlowResult(flow_id=fid, paths=paths, delivered=0.0, unserved=0.0, cause="NONE")
        for fid, paths in paths_by_flow.items()
    }
    return Allocation(results=results, arc_load={})


def test_previous_allocation_is_ignored():
    prev_a = previous({"F1": [PathAlloc(arcs=["L_AC:A>C", "L_CD:C>D"], rate=15)]})
    prev_b = previous({"F1": [PathAlloc(arcs=["L_AB:A>B", "L_BD:B>D"], rate=3)], "F2": []})
    one = run(allocate, diamond(), [F1, F2], S2, prev=prev_a)
    two = run(allocate, diamond(), [F1, F2], S2, prev=prev_b)
    assert one.outcomes == two.outcomes and one.arc_load == two.arc_load


def test_repeat_run_is_identical_whatever_the_input_order():
    flows = [F1, F2, flow("F0", "B", "C", 4, 1)]
    first = run(allocate, diamond(), flows, S2)
    assert run(allocate, diamond(), flows, S2).outcomes == first.outcomes
    assert run(allocate, list(reversed(diamond())), list(reversed(flows)), S2).outcomes == first.outcomes


# --- input validation -------------------------------------------------------------------


def test_duplicate_flow_ids_are_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        run(allocate, diamond(), [F1, F1], S2)


def test_negative_rate_is_rejected():
    with pytest.raises(ValueError, match="negative"):
        run(allocate, diamond(), [flow("X", "A", "D", -1, 0)], S2)


@pytest.mark.parametrize(
    "kwargs",
    [{"order": "random"}, {"max_paths": 0}, {"congestion_lambda": -1}, {"util_cap": 0}, {"util_cap": 1.5}],
)
def test_bad_config_is_rejected(kwargs):
    with pytest.raises(ValueError):
        run(allocate, diamond(), [F1], PolicyConfig(**kwargs))


def test_allocator_routes_on_latency_not_hop_count():
    # A-D direct is one hop but 10 ms; A-B-D is two hops and 2 ms.
    links = link("L1", "A", "D", 10, 10) + link("L2", "A", "B", 10, 1) + link("L3", "B", "D", 10, 1)
    outcome = run(allocate, links, [flow("X", "A", "D", 5, 0)], S2).outcomes["X"]
    assert node_paths(outcome) == [["A", "B", "D"]]


def test_disconnected_flow_with_a_previous_path_has_no_reference_path():
    # Both links out of A are down. F1's old path crossed L_AB, so the failed link is named, but
    # the flow is disconnected: the record shows no reference path and no cut.
    prev = previous({"F1": [PathAlloc(arcs=["L_AB:A>B", "L_BD:B>D"], rate=15)]})
    record = run(allocate, diamond(down=("L_AB", "L_AC")), [F1], S2, prev=prev).records[0]
    assert record.failed_links == ["L_AB"]
    assert (record.cause, record.reference_path, record.reference_status) == ("DISCONNECTED", [], "NONE: disconnected")
    assert record.cut == [] and (record.maxflow_bound, record.greedy_gap) == (0, 0.0)
