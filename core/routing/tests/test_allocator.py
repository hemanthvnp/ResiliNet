from dataclasses import replace

import pytest

from core.routing.allocator import allocate
from core.routing.inputs import AllocConfig, FlowSpec, PathRate
from core.routing.tests.helpers import (
    CASES,
    EXPECTED,
    F1,
    F2,
    blocking_arcs,
    blocking_flow,
    diamond,
    link,
    node_paths,
    nodes,
    random_case,
)

S2 = AllocConfig(order="class_size_desc", max_paths=3, congestion_lambda=0, util_cap=1.0)


def rates(outcome):
    return [p.rate for p in outcome.paths]


# --- the diamond, both rows (expected_diamond.json) -------------------------------------


@pytest.mark.parametrize("case, down", [("healthy", ()), ("bd_failed", ("L_BD",))])
def test_s2_matches_expected_table(case, down):
    expected = EXPECTED["cases"][case]["S2"]
    result = allocate(diamond(down), [F1, F2], S2)
    for flow_id in ("F1", "F2"):
        outcome = result.outcomes[flow_id]
        assert node_paths(outcome) == expected["paths"][flow_id]
        assert rates(outcome) == expected["rates"][flow_id]
        assert outcome.delivered == expected["delivered"][flow_id]
        assert outcome.unserved == expected["unserved"][flow_id]
        assert outcome.cause == expected["cause"][flow_id]


def test_healthy_diamond_loads_are_within_capacity():
    result = allocate(diamond(), [F1, F2], S2)
    assert result.arc_load == {"L_AB:A>B": 10, "L_AC:A>C": 10, "L_BD:B>D": 10, "L_CD:C>D": 10}


def test_path_limit_case_matches_expected_cases():
    expected = CASES["path_limit"]
    result = allocate(diamond(), [F1], AllocConfig(max_paths=expected["max_paths"]))
    outcome = result.outcomes["F1"]
    assert node_paths(outcome) == expected["paths"] and rates(outcome) == expected["rates"]
    assert (outcome.delivered, outcome.unserved, outcome.cause) == (
        expected["delivered"], expected["unserved"], expected["cause"],
    )


# --- hard constraints ----------------------------------------------------------------------


def test_util_cap_case_matches_expected_cases():
    expected = CASES["util_cap"]
    arcs = link("L1", "A", "B", expected["capacity"], 1)
    flow = FlowSpec("X", "A", "B", expected["rate"], 0)
    result = allocate(arcs, [flow], AllocConfig(util_cap=expected["util_cap"]))
    outcome = result.outcomes["X"]
    assert (outcome.delivered, outcome.unserved, outcome.cause) == (
        expected["delivered"], expected["unserved"], expected["cause"],
    )
    assert result.arc_load == expected["arc_load"]


def test_util_cap_rounding_is_exact():
    # floor(0.29 * 100) is 29 (the float product is 28.999999999999996).
    arcs = link("L1", "A", "B", 100, 1)
    result = allocate(arcs, [FlowSpec("X", "A", "B", 100, 0)], AllocConfig(util_cap=0.29))
    assert result.outcomes["X"].delivered == 29


@pytest.mark.parametrize("seed", range(60))
def test_hard_constraints_hold_on_random_inputs(seed):
    arcs, flows, cfg = random_case(seed)
    by_id = {a.id: a for a in arcs}
    result = allocate(arcs, flows, cfg)
    context = f"seed={seed} cfg={cfg}"
    load: dict[str, int] = {}
    for f in flows:
        outcome = result.outcomes[f.id]
        assert len(outcome.paths) <= cfg.max_paths, context
        assert outcome.delivered + outcome.unserved == f.rate, context
        assert sum(p.rate for p in outcome.paths) == outcome.delivered or f.src == f.dst, context
        for p in outcome.paths:
            assert all(by_id[a].up for a in p.arcs), context
            walk = nodes(p.arcs)
            assert walk[0] == f.src and walk[-1] == f.dst and len(set(walk)) == len(walk), context
            for a in p.arcs:
                load[a] = load.get(a, 0) + p.rate
    for arc_id, value in load.items():
        assert value <= int(by_id[arc_id].capacity * cfg.util_cap + 1e-9), context
    assert result.arc_load == dict(sorted(load.items())), context
    assert len(result.records) == len(flows), context


@pytest.mark.parametrize("seed", range(30))
def test_removing_lower_classes_changes_nothing_above(seed):
    arcs, flows, cfg = random_case(seed)
    cfg = replace(cfg, order="class_size_desc")
    full = allocate(arcs, flows, cfg)
    for cutoff in (0, 1):  # drop every class above `cutoff`
        kept = [f for f in flows if f.cls <= cutoff]
        reduced = allocate(arcs, kept, cfg)
        for f in kept:
            assert reduced.outcomes[f.id].paths == full.outcomes[f.id].paths, f"seed={seed} cutoff={cutoff}"


# --- ordering and cost ------------------------------------------------------------------


def test_class_order_places_critical_flow_first():
    # One arc of capacity 10; the P2 flow comes first in the input but P0 is placed first.
    arcs = link("L1", "A", "B", 10, 1)
    flows = [FlowSpec("low", "A", "B", 10, 2), FlowSpec("crit", "A", "B", 10, 0)]
    result = allocate(arcs, flows, S2)
    assert result.outcomes["crit"].delivered == 10 and result.outcomes["low"].delivered == 0
    assert list(result.outcomes) == ["crit", "low"]


def test_arrival_order_ignores_class():
    arcs = link("L1", "A", "B", 10, 1)
    flows = [FlowSpec("low", "A", "B", 10, 2), FlowSpec("crit", "A", "B", 10, 0)]
    result = allocate(arcs, flows, AllocConfig(order="arrival"))
    assert result.outcomes["low"].delivered == 10 and result.outcomes["crit"].delivered == 0


def congestion_case(congestion_lambda):
    # G1 (9 Mbps) takes A-B-D. G2 (5 Mbps) then sees A-B-D at 90% utilization.
    flows = [FlowSpec("G1", "A", "D", 9, 0), FlowSpec("G2", "A", "D", 5, 0)]
    return allocate(diamond(), flows, AllocConfig(max_paths=3, congestion_lambda=congestion_lambda))


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
    result = allocate(diamond(down=("L_AB", "L_AC")), [F1], S2)
    outcome = result.outcomes["F1"]
    assert (outcome.paths, outcome.delivered, outcome.unserved, outcome.cause) == ((), 0.0, 15.0, "DISCONNECTED")
    assert result.records[0].attempts == ()  # no path search was attempted


def test_unknown_destination_is_disconnected():
    outcome = allocate(diamond(), [FlowSpec("X", "A", "Z", 5, 0)], S2).outcomes["X"]
    assert outcome.cause == "DISCONNECTED"


def test_blocking_example_matches_expected_cases():
    expected = CASES["blocking"]
    outcome = allocate(blocking_arcs(), [blocking_flow()], S2).outcomes["X"]
    assert node_paths(outcome) == expected["paths"] and rates(outcome) == expected["rates"]
    assert (outcome.delivered, outcome.unserved, outcome.cause) == (
        expected["delivered"], expected["unserved"], expected["cause"],
    )


def test_same_source_and_destination_is_delivered_without_load():
    result = allocate(diamond(), [FlowSpec("X", "A", "A", 7, 0)], S2)
    outcome = result.outcomes["X"]
    assert (outcome.paths, outcome.delivered, outcome.unserved, outcome.cause) == ((), 7.0, 0.0, "NONE")
    assert result.arc_load == {}


def test_zero_rate_flow():
    outcome = allocate(diamond(), [FlowSpec("X", "A", "D", 0, 0)], S2).outcomes["X"]
    assert (outcome.paths, outcome.delivered, outcome.unserved, outcome.cause) == ((), 0.0, 0.0, "NONE")


# --- purity ------------------------------------------------------------------------------


def test_previous_allocation_is_ignored():
    prev_a = {"F1": [PathRate(("L_AC:A>C", "L_CD:C>D"), 15)]}
    prev_b = {"F1": [PathRate(("L_AB:A>B", "L_BD:B>D"), 3)], "F2": []}
    one = allocate(diamond(), [F1, F2], S2, prev=prev_a)
    two = allocate(diamond(), [F1, F2], S2, prev=prev_b)
    assert one.outcomes == two.outcomes and one.arc_load == two.arc_load


def test_repeat_run_is_identical_whatever_the_input_order():
    flows = [F1, F2, FlowSpec("F0", "B", "C", 4, 1)]
    first = allocate(diamond(), flows, S2)
    assert allocate(diamond(), flows, S2).outcomes == first.outcomes
    assert allocate(list(reversed(diamond())), list(reversed(flows)), S2).outcomes == first.outcomes


# --- input validation -------------------------------------------------------------------


def test_duplicate_flow_ids_are_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        allocate(diamond(), [F1, F1], S2)


def test_negative_rate_is_rejected():
    with pytest.raises(ValueError, match="negative"):
        allocate(diamond(), [FlowSpec("X", "A", "D", -1, 0)], S2)


@pytest.mark.parametrize(
    "kwargs",
    [{"order": "random"}, {"max_paths": 0}, {"congestion_lambda": -1}, {"util_cap": 0}, {"util_cap": 1.5}],
)
def test_bad_config_is_rejected(kwargs):
    with pytest.raises(ValueError):
        AllocConfig(**kwargs)
