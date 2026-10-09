import pytest

from core.routing.baselines import route_s0, route_s0_qos
from core.routing.inputs import FlowSpec
from core.routing.tests.helpers import EXPECTED, F1, F2, diamond, link, node_paths

CASES = {"healthy": (), "bd_failed": ("L_BD",)}
ROUTES = {"S0": route_s0, "S0-QoS": route_s0_qos}


def one_arc(capacity=10):
    return link("L1", "A", "B", capacity, 1)


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("policy", ROUTES)
def test_diamond_matches_expected_table(case, policy):
    expected = EXPECTED["cases"][case][policy]
    result = ROUTES[policy](diamond(down=CASES[case]), [F1, F2])
    for flow_id, delivered in expected["delivered"].items():
        assert result.outcomes[flow_id].delivered == pytest.approx(delivered, abs=1e-9)
        assert node_paths(result.outcomes[flow_id]) == expected["paths"][flow_id]
    if "arc_load" in expected:
        assert result.arc_load == expected["arc_load"]


def test_s0_overloaded_flows_have_overload_loss():
    result = route_s0(diamond(), [F1, F2])
    assert {o.cause for o in result.outcomes.values()} == {"OVERLOAD_LOSS"}
    assert result.outcomes["F1"].unserved == pytest.approx(9)
    assert result.outcomes["F2"].unserved == pytest.approx(6)


def test_qos_critical_flow_loses_only_what_does_not_fit():
    result = route_s0_qos(diamond(), [F1, F2])
    assert (result.outcomes["F1"].cause, result.outcomes["F2"].cause) == ("OVERLOAD_LOSS", "OVERLOAD_LOSS")


def test_disconnected_flow_has_no_path():
    result = route_s0(diamond(down=("L_AB", "L_AC")), [F1])
    outcome = result.outcomes["F1"]
    assert outcome.paths == () and outcome.delivered == 0 and outcome.cause == "DISCONNECTED"
    assert result.arc_load == {}


def test_non_integer_delivery():
    # Capacity 10 and offered load 7 + 18 = 25 give scale 10/25 = 0.4: 7 -> 2.8 and 18 -> 7.2.
    flows = [FlowSpec("X", "A", "B", 7, 1), FlowSpec("Y", "A", "B", 18, 1)]
    result = route_s0(one_arc(), flows)
    assert result.outcomes["X"].delivered == pytest.approx(2.8, abs=1e-9)
    assert result.outcomes["X"].unserved == pytest.approx(4.2, abs=1e-9)


def test_no_overload_delivers_in_full():
    for policy in ROUTES.values():
        outcome = policy(one_arc(), [FlowSpec("X", "A", "B", 10, 1)]).outcomes["X"]
        assert (outcome.delivered, outcome.unserved, outcome.cause) == (10.0, 0.0, "NONE")


def test_qos_routes_and_load_equal_s0():
    flows = [F1, F2, FlowSpec("F3", "B", "D", 4, 1)]
    s0, qos = route_s0(diamond(), flows), route_s0_qos(diamond(), flows)
    assert s0.arc_load == qos.arc_load
    for flow_id in s0.outcomes:
        assert s0.outcomes[flow_id].paths == qos.outcomes[flow_id].paths


def test_qos_higher_classes_unchanged_when_p2_removed():
    # Capacity 10; P0 6, P1 6, P2 6. P0 gets 6, P1 gets the 4 left, P2 gets 0.
    flows = [FlowSpec("a", "A", "B", 6, 0), FlowSpec("b", "A", "B", 6, 1), FlowSpec("c", "A", "B", 6, 2)]
    full = route_s0_qos(one_arc(), flows)
    without_p2 = route_s0_qos(one_arc(), flows[:2])
    assert full.outcomes["a"].delivered == pytest.approx(6)
    assert full.outcomes["b"].delivered == pytest.approx(4)
    assert full.outcomes["c"].delivered == pytest.approx(0)
    for flow_id in ("a", "b"):
        assert without_p2.outcomes[flow_id].delivered == full.outcomes[flow_id].delivered


def test_same_input_same_output_whatever_the_flow_order():
    flows = [F1, F2, FlowSpec("F0", "A", "C", 3, 1)]
    for policy in ROUTES.values():
        first = policy(diamond(), flows)
        assert policy(diamond(), flows).outcomes == first.outcomes
        assert policy(diamond(), list(reversed(flows))).outcomes == first.outcomes


def test_source_equals_destination_is_delivered_without_load():
    outcome_result = route_s0(one_arc(), [FlowSpec("X", "A", "A", 7, 0)])
    assert outcome_result.outcomes["X"].delivered == 7 and outcome_result.arc_load == {}


def test_zero_rate_flow_does_not_divide_by_zero():
    for policy in ROUTES.values():
        result = policy(one_arc(), [FlowSpec("Z", "A", "B", 0, 0)])
        assert result.outcomes["Z"].delivered == 0 and result.outcomes["Z"].cause == "NONE"


def test_baseline_records_are_subset_records():
    for policy in ROUTES.values():
        result = policy(diamond(), [F1, F2])
        assert [r.flow_id for r in result.records] == ["F1", "F2"]
        for record in result.records:
            assert record.attempts == () and record.cut == ()
            assert record.maxflow_bound is None and record.greedy_gap is None


def test_baselines_reject_duplicate_ids_and_negative_rates():
    for policy in ROUTES.values():
        with pytest.raises(ValueError, match="duplicate"):
            policy(diamond(), [F1, F1])
        with pytest.raises(ValueError, match="negative"):
            policy(diamond(), [FlowSpec("X", "A", "D", -1, 0)])
