import pytest

from core.routing.baselines import route_s0, route_s0_qos
from core.routing.tests.helpers import EXPECTED, F1, F2, diamond, flow, link, loaded, node_paths, run

CASES = {"healthy": (), "bd_failed": ("L_BD",)}
ROUTES = {"S0": route_s0, "S0-QoS": route_s0_qos}


def one_arc(capacity=10):
    return link("L1", "A", "B", capacity, 1)


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("policy", ROUTES)
def test_diamond_matches_expected_table(case, policy):
    expected = EXPECTED["cases"][case][policy]
    result = run(ROUTES[policy], diamond(down=CASES[case]), [F1, F2])
    for flow_id, delivered in expected["delivered"].items():
        assert result.outcomes[flow_id].delivered == pytest.approx(delivered, abs=1e-9)
        assert node_paths(result.outcomes[flow_id]) == expected["paths"][flow_id]
    if "arc_load" in expected:
        assert loaded(result.arc_load) == expected["arc_load"]


def test_s0_overloaded_flows_have_overload_loss():
    result = run(route_s0, diamond(), [F1, F2])
    assert {o.cause for o in result.outcomes.values()} == {"OVERLOAD_LOSS"}
    assert result.outcomes["F1"].unserved == pytest.approx(9)
    assert result.outcomes["F2"].unserved == pytest.approx(6)


def test_qos_critical_flow_loses_only_what_does_not_fit():
    result = run(route_s0_qos, diamond(), [F1, F2])
    assert (result.outcomes["F1"].cause, result.outcomes["F2"].cause) == ("OVERLOAD_LOSS", "OVERLOAD_LOSS")


def test_disconnected_flow_has_no_path():
    result = run(route_s0, diamond(down=("L_AB", "L_AC")), [F1])
    outcome = result.outcomes["F1"]
    assert outcome.paths == [] and outcome.delivered == 0 and outcome.cause == "DISCONNECTED"
    assert loaded(result.arc_load) == {}


def test_non_integer_delivery():
    # Capacity 10 and offered load 7 + 18 = 25 give scale 10/25 = 0.4: 7 -> 2.8 and 18 -> 7.2.
    flows = [flow("X", "A", "B", 7, 1), flow("Y", "A", "B", 18, 1)]
    result = run(route_s0, one_arc(), flows)
    assert result.outcomes["X"].delivered == pytest.approx(2.8, abs=1e-9)
    assert result.outcomes["X"].unserved == pytest.approx(4.2, abs=1e-9)


def test_no_overload_delivers_in_full():
    for policy in ROUTES.values():
        outcome = run(policy, one_arc(), [flow("X", "A", "B", 10, 1)]).outcomes["X"]
        assert (outcome.delivered, outcome.unserved, outcome.cause) == (10.0, 0.0, "NONE")


def test_qos_routes_and_load_equal_s0():
    flows = [F1, F2, flow("F3", "B", "D", 4, 1)]
    s0, qos = run(route_s0, diamond(), flows), run(route_s0_qos, diamond(), flows)
    assert s0.arc_load == qos.arc_load
    for flow_id in s0.outcomes:
        assert s0.outcomes[flow_id].paths == qos.outcomes[flow_id].paths


def test_qos_higher_classes_unchanged_when_p2_removed():
    # Capacity 10; P0 6, P1 6, P2 6. P0 gets 6, P1 gets the 4 left, P2 gets 0.
    flows = [flow("a", "A", "B", 6, 0), flow("b", "A", "B", 6, 1), flow("c", "A", "B", 6, 2)]
    full = run(route_s0_qos, one_arc(), flows)
    without_p2 = run(route_s0_qos, one_arc(), flows[:2])
    assert full.outcomes["a"].delivered == pytest.approx(6)
    assert full.outcomes["b"].delivered == pytest.approx(4)
    assert full.outcomes["c"].delivered == pytest.approx(0)
    for flow_id in ("a", "b"):
        assert without_p2.outcomes[flow_id].delivered == full.outcomes[flow_id].delivered


def test_same_input_same_output_whatever_the_flow_order():
    flows = [F1, F2, flow("F0", "A", "C", 3, 1)]
    for policy in ROUTES.values():
        first = run(policy, diamond(), flows)
        assert run(policy, diamond(), flows).outcomes == first.outcomes
        assert run(policy, diamond(), list(reversed(flows))).outcomes == first.outcomes


def test_source_equals_destination_is_delivered_without_load():
    result = run(route_s0, one_arc(), [flow("X", "A", "A", 7, 0)])
    assert result.outcomes["X"].delivered == 7 and loaded(result.arc_load) == {}


def test_zero_rate_flow_does_not_divide_by_zero():
    for policy in ROUTES.values():
        result = run(policy, one_arc(), [flow("Z", "A", "B", 0, 0)])
        assert result.outcomes["Z"].delivered == 0 and result.outcomes["Z"].cause == "NONE"


def test_baseline_records_are_subset_records():
    for policy in ROUTES.values():
        result = run(policy, diamond(), [F1, F2])
        assert [r.flow_id for r in result.records] == ["F1", "F2"]
        for record in result.records:
            assert record.attempts == [] and record.cut == []
            assert record.maxflow_bound is None and record.greedy_gap is None


def test_baselines_reject_duplicate_ids_and_negative_rates():
    for policy in ROUTES.values():
        with pytest.raises(ValueError, match="duplicate"):
            run(policy, diamond(), [F1, F1])
        with pytest.raises(ValueError, match="negative"):
            run(policy, diamond(), [flow("X", "A", "D", -1, 0)])


def test_baselines_route_on_latency_not_hop_count():
    # A-D direct is one hop but 10 ms; A-B-D is two hops and 2 ms.
    links = link("L1", "A", "D", 10, 10) + link("L2", "A", "B", 10, 1) + link("L3", "B", "D", 10, 1)
    for policy in ROUTES.values():
        outcome = run(policy, links, [flow("X", "A", "D", 5, 0)]).outcomes["X"]
        assert node_paths(outcome) == [["A", "B", "D"]]


def test_baseline_records_name_the_failed_link_a_previous_path_crossed():
    from core.model.types import Allocation, FlowResult, PathAlloc

    previous = PathAlloc(arcs=["L_AB:A>B", "L_BD:B>D"], rate=15)
    prev = Allocation(
        results={"F1": FlowResult(flow_id="F1", paths=[previous], delivered=6.0, unserved=9.0, cause="OVERLOAD_LOSS")},
        arc_load={},
    )
    for policy in ROUTES.values():
        record = run(policy, diamond(down=("L_BD",)), [F1], prev=prev).records[0]
        assert record.failed_links == ["L_BD"] and record.previous == [previous]
        assert record.reference_status == "INVALID: L_BD down"
        assert record.reference_path == ["L_AB:A>B", "L_BD:B>D"]
