import pytest

from core.routing.inputs import FlowSpec
from core.routing.ordering import order_flows


def ids(flows):
    return [f.id for f in flows]


P2_FIRST = [FlowSpec("a", "A", "D", 5, 2), FlowSpec("b", "A", "D", 5, 0)]


def test_critical_flow_placed_first_under_class_order():
    assert ids(order_flows(P2_FIRST, "class_size_desc")) == ["b", "a"]


def test_arrival_ignores_class():
    assert ids(order_flows(P2_FIRST, "arrival")) == ["a", "b"]


def test_size_desc_and_asc_within_class():
    flows = [FlowSpec("s", "A", "D", 2, 1), FlowSpec("l", "A", "D", 9, 1), FlowSpec("m", "A", "D", 5, 1)]
    assert ids(order_flows(flows, "class_size_desc")) == ["l", "m", "s"]
    assert ids(order_flows(flows, "class_size_asc")) == ["s", "m", "l"]


def test_class_beats_size():
    flows = [FlowSpec("big", "A", "D", 99, 1), FlowSpec("small", "A", "D", 1, 0)]
    assert ids(order_flows(flows, "class_size_desc")) == ["small", "big"]


def test_flow_id_is_the_last_key():
    flows = [FlowSpec("z", "A", "D", 5, 0), FlowSpec("a", "A", "D", 5, 0)]
    assert ids(order_flows(flows, "class_size_desc")) == ["a", "z"]
    assert ids(order_flows(list(reversed(flows)), "class_size_asc")) == ["a", "z"]


def test_unknown_order_raises():
    with pytest.raises(ValueError):
        order_flows(P2_FIRST, "random")


def test_class_beats_size_in_ascending_order_too():
    flows = [FlowSpec("a", "A", "D", 1, 1), FlowSpec("b", "A", "D", 9, 0)]
    assert ids(order_flows(flows, "class_size_asc")) == ["b", "a"]
