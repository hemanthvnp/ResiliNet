import pytest

from core.routing.ordering import order_flows
from core.routing.tests.helpers import flow


def ids(flows):
    return [f.id for f in flows]


P2_FIRST = [flow("a", "A", "D", 5, 2), flow("b", "A", "D", 5, 0)]


def test_critical_flow_placed_first_under_class_order():
    assert ids(order_flows(P2_FIRST, "class_size_desc")) == ["b", "a"]


def test_arrival_ignores_class():
    assert ids(order_flows(P2_FIRST, "arrival")) == ["a", "b"]


def test_size_desc_and_asc_within_class():
    flows = [flow("s", "A", "D", 2, 1), flow("l", "A", "D", 9, 1), flow("m", "A", "D", 5, 1)]
    assert ids(order_flows(flows, "class_size_desc")) == ["l", "m", "s"]
    assert ids(order_flows(flows, "class_size_asc")) == ["s", "m", "l"]


def test_class_beats_size():
    flows = [flow("big", "A", "D", 99, 1), flow("small", "A", "D", 1, 0)]
    assert ids(order_flows(flows, "class_size_desc")) == ["small", "big"]


def test_flow_id_is_the_last_key():
    flows = [flow("z", "A", "D", 5, 0), flow("a", "A", "D", 5, 0)]
    assert ids(order_flows(flows, "class_size_desc")) == ["a", "z"]
    assert ids(order_flows(list(reversed(flows)), "class_size_asc")) == ["a", "z"]


def test_unknown_order_raises():
    with pytest.raises(ValueError):
        order_flows(P2_FIRST, "random")


def test_class_beats_size_in_ascending_order_too():
    flows = [flow("a", "A", "D", 1, 1), flow("b", "A", "D", 9, 0)]
    assert ids(order_flows(flows, "class_size_asc")) == ["b", "a"]
