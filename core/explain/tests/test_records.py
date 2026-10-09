from pathlib import Path

import pytest

from core.explain.bound import greedy_gap, maxflow_bound
from core.explain.cut import residual_cut
from core.explain.template import explain
from core.model.types import Allocation, CutArc, DecisionRecord, FlowResult, PathAlloc, PolicyConfig, Topology
from core.routing.allocator import allocate
from core.routing.baselines import route_s0
from core.routing.tests.helpers import (
    F1,
    F2,
    RECORDS,
    blocking_flow,
    blocking_links,
    cut_view,
    diamond,
    flow,
    link,
    random_case,
    run,
)

S2 = PolicyConfig()
FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"


def section_10_fixture() -> DecisionRecord:
    text = (FIXTURES / "decisions" / "section10_f12.json").read_text(encoding="utf-8")
    return DecisionRecord.model_validate_json(text)


def section_10_run():
    """The frozen diamond with L7 down and F12's previous path across it, as in PLAN.md section 10."""
    topo = Topology.model_validate_json((FIXTURES / "topologies" / "diamond.json").read_text(encoding="utf-8"))
    links = [lk.model_copy(update={"status": "down"}) if lk.id == "L7" else lk for lk in topo.links]
    topo = topo.model_copy(update={"links": links})
    previous = PathAlloc(arcs=["L2:A>B", "L7:B>D"], rate=10)
    prev = Allocation(
        results={"F12": FlowResult(flow_id="F12", paths=[previous], delivered=10.0, unserved=5.0, cause="NONE")},
        arc_load={},
    )
    return run(allocate, topo, [flow("F12", "A", "D", 15, 0)], S2, prev=prev, step=2)


def test_builder_reproduces_the_frozen_section_10_record_exactly():
    # fixtures/decisions/section10_f12.json is B's frozen copy of the PLAN.md section 10 record.
    assert section_10_run().records[0] == section_10_fixture()


def test_one_record_per_flow_with_unique_ids():
    flows = [F1, F2, flow("F3", "B", "C", 1, 1)]
    records = run(allocate, diamond(), flows, S2).records
    assert len(records) == 3 and len({r.flow_id for r in records}) == 3


# --- reference path and status -------------------------------------------------------------


def status(result, flow_id):
    return next(r for r in result.records if r.flow_id == flow_id).reference_status


def test_status_used():
    assert status(run(allocate, diamond(), [flow("X", "A", "D", 10, 0)], S2), "X") == "USED"


def test_status_partial_names_the_arc_where_residual_ran_out():
    # F1 needs 15, A-B-D has 10 on every arc: the first arc on the path is named.
    assert status(run(allocate, diamond(), [F1], S2), "F1") == "PARTIAL: L_AB:A>B saturated"


def test_status_invalid_names_the_down_link():
    assert section_10_run().records[0].reference_status == "INVALID: L7 down"


def test_status_none_when_disconnected():
    result = run(allocate, diamond(down=("L_AB", "L_AC")), [F1], S2)
    assert result.records[0].reference_status == "NONE: disconnected"
    assert result.records[0].reference_path == []


def test_previous_paths_and_failed_links_are_copied():
    record = section_10_run().records[0]
    assert record.previous == [PathAlloc(arcs=["L2:A>B", "L7:B>D"], rate=10)] and record.failed_links == ["L7"]


def test_failed_links_are_only_those_the_flows_previous_paths_crossed():
    # L_BD is down, but F1 never used it, so its record does not list it as failed.
    prev = Allocation(
        results={"F1": FlowResult(flow_id="F1", paths=[PathAlloc(arcs=["L_AC:A>C", "L_CD:C>D"], rate=10)],
                                  delivered=10.0, unserved=5.0, cause="NONE")},
        arc_load={},
    )
    record = run(allocate, diamond(down=("L_BD",)), [F1], S2, prev=prev).records[0]
    assert record.failed_links == [] and record.reference_status == "PARTIAL: L_AC:A>C saturated"


# --- attempts -----------------------------------------------------------------------------


def test_two_attempts_for_f1_on_healthy_diamond():
    record = run(allocate, diamond(), [F1], S2).records[0]
    assert [(a.iter, a.pushed) for a in record.attempts] == [(1, 10), (2, 5)]
    assert sum(a.pushed for a in record.attempts) == record.delivered == 15


# --- bound, gap and cut -------------------------------------------------------------------


def check_against(record, key):
    expected = RECORDS[key]
    assert (record.maxflow_bound, record.greedy_gap) == (expected["maxflow_bound"], expected["greedy_gap"]), key
    assert cut_view(record) == expected["cut"], key
    if "explanation" in expected:
        assert record.explanation == expected["explanation"], key


def test_bd_failed_diamond_matches_expected_records():
    check_against(run(allocate, diamond(down=("L_BD",)), [F1], S2).records[0], "bd_failed_F1")


def test_path_limit_diamond_matches_expected_records():
    record = run(allocate, diamond(), [F1], PolicyConfig(max_paths=1)).records[0]
    assert record.cause == "PATH_LIMIT"
    check_against(record, "path_limit_F1")


def test_healthy_diamond_second_flow_matches_expected_records():
    record = run(allocate, diamond(), [F1, F2], S2).records[1]
    assert record.flow_id == "F2"
    check_against(record, "healthy_F2")


def test_disconnected_bound_and_gap_are_zero():
    record = run(allocate, diamond(down=("L_AB", "L_AC")), [F1], S2).records[0]
    assert (record.maxflow_bound, record.greedy_gap) == (0, 0.0)


def test_fully_served_flow_has_no_bound():
    record = run(allocate, diamond(), [flow("X", "A", "D", 10, 0)], S2).records[0]
    assert (record.maxflow_bound, record.greedy_gap) == (None, None)


def test_gap_is_never_negative_on_random_inputs():
    for seed in range(60):
        topo, flows, cfg = random_case(seed)
        for record in run(allocate, topo, flows, cfg).records:
            if record.greedy_gap is not None:
                assert record.greedy_gap >= 0, f"seed={seed} flow={record.flow_id}"
                assert record.maxflow_bound is not None and record.maxflow_bound <= record.demand, f"seed={seed}"


def test_cut_holds_load_by_class():
    record = section_10_run().records[0]
    assert [(c.arc, c.state, c.load_by_class) for c in record.cut] == [
        ("L5:A>C", "saturated", {0: 10}),
        ("L7:B>D", "down", {}),
    ]


def test_cut_is_empty_unless_insufficient_capacity():
    path_limit = run(allocate, diamond(), [F1], PolicyConfig(max_paths=1)).records[0]
    disconnected = run(allocate, diamond(down=("L_AB", "L_AC")), [F1], S2).records[0]
    served = run(allocate, diamond(), [flow("X", "A", "D", 10, 0)], S2).records[0]
    assert (path_limit.cut, disconnected.cut, served.cut) == ([], [], [])


def test_cut_is_sorted_by_arc_id():
    cut = residual_cut(
        [("L9:A>B", "A", "B", 0), ("L1:A>C", "A", "C", 0)],
        [("L5:A>D", "A", "D")],
        "A",
        lambda arcs: {},
    )
    assert [c.arc for c in cut] == ["L1:A>C", "L5:A>D", "L9:A>B"]


def test_blocking_example_matches_expected_records_and_makes_no_physical_claim():
    record = run(allocate, blocking_links(), [blocking_flow()], S2).records[0]
    check_against(record, "blocking")
    assert "could have been routed (heuristic or path limit)" in record.explanation
    assert "cut" not in record.explanation


def test_maxflow_bound_adds_back_own_reservations():
    # After a flow holds 10 on a 10-capacity arc the residual is 0; adding it back gives 10.
    own = [PathAlloc(arcs=["L1:A>B"], rate=10)]
    assert maxflow_bound([("L1:A>B", "A", "B", 0)], own, "A", "B", 15) == 10
    assert greedy_gap(10, 4.0) == 6.0


# --- template -----------------------------------------------------------------------------


def record_with(**changes) -> DecisionRecord:
    return section_10_run().records[0].model_copy(update=changes)


def test_first_two_sentences_of_section_10_line():
    assert explain(record_with()).startswith(
        "F12 (P0, 15 Mbps): path A-B-D invalid (L7 down). Moved 10 Mbps to A-C-D (latency 4 ms)."
    )


def test_heuristic_wording_when_gap_above_zero():
    text = explain(record_with(unserved=5.0, greedy_gap=5.0))
    assert text.endswith("5 Mbps unserved, of which 5 Mbps could have been routed (heuristic or path limit).")
    assert "cut" not in text


def test_disconnected_wording_names_no_cut():
    record = run(allocate, diamond(down=("L_AB", "L_AC")), [F1], S2).records[0]
    assert record.explanation == "F1 (P0, 15 Mbps): 15 Mbps unserved: destination unreachable."


def test_overload_loss_wording():
    record = run(route_s0, diamond(), [F1, F2]).records[0]
    assert record.explanation == "F1 (P0, 15 Mbps): path A-B-D used. 9 Mbps lost to overload."


def test_non_integer_rates_use_two_decimals():
    record = record_with(unserved=4.2, greedy_gap=None, cut=[])
    assert explain(record).endswith("4.20 Mbps unserved.")


def test_same_record_same_text():
    record = record_with()
    assert explain(record) == explain(record)


@pytest.mark.parametrize("seed", range(5))
def test_whole_run_is_text_identical(seed):
    topo, flows, cfg = random_case(seed)
    first = [r.explanation for r in run(allocate, topo, flows, cfg).records]
    assert first == [r.explanation for r in run(allocate, topo, flows, cfg).records]


# --- classes in the cut and wording ---------------------------------------------------------


def test_cut_names_every_class_holding_the_arc_in_ascending_order():
    # One arc of capacity 10 is filled by P0 (7) and P1 (3); the P2 flow is left with nothing.
    flows = [flow("a", "A", "B", 7, 0), flow("b", "A", "B", 3, 1), flow("z", "A", "B", 5, 2)]
    record = run(allocate, link("L1", "A", "B", 10, 1), flows, S2).records[-1]
    assert record.flow_id == "z"
    assert [(c.arc, c.state, c.load_by_class) for c in record.cut] == [("L1:A>B", "saturated", {0: 7, 1: 3})]
    assert record.explanation == (
        "z (P2, 5 Mbps): path A-B limited by L1 (saturated). "
        "5 Mbps unserved: cut L1 saturated by P0 (7 Mbps), P1 (3 Mbps)."
    )


def test_class_order_in_text_does_not_depend_on_dict_order():
    cut = [CutArc(arc="L5:A>C", state="saturated", load_by_class={1: 3, 0: 7})]
    assert explain(record_with(cut=cut)).endswith("cut L5 saturated by P0 (7 Mbps), P1 (3 Mbps).")


def test_no_cut_under_path_limit_even_when_part_of_the_network_is_cut_off():
    # Node E hangs off D by a zero-capacity link, so it is unreachable and a cut computed
    # for this flow would not be empty. Under PATH_LIMIT none may be reported.
    links = diamond() + link("L_DE", "D", "E", 0, 1)
    record = run(allocate, links, [F1], PolicyConfig(max_paths=1)).records[0]
    assert record.cause == "PATH_LIMIT" and record.cut == []


def test_first_placement_says_placed_and_a_move_says_moved():
    placed = run(allocate, diamond(), [flow("X", "A", "D", 10, 0)], S2).records[0].explanation
    assert placed == "X (P0, 10 Mbps): path A-B-D used. Placed 10 Mbps to A-B-D (latency 2 ms)."
    assert " Moved " in section_10_run().records[0].explanation
