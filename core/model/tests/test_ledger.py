"""Tests for the capacity ledger (spec: capacity-ledger).

Expected values are the hand-worked numbers in the capacity-ledger spec scenarios.
"""

import pytest

from core.model.ledger import CapacityExceeded, Ledger, effective_capacity
from core.model.types import Link, Node, Topology


def topology(*links):
    names = sorted({n for l in links for n in (l.u, l.v)})
    return Topology(nodes=[Node(id=n, type="switch", name=n) for n in names], links=list(links))


def link(id, u, v, capacity, status="up"):
    return Link(id=id, u=u, v=v, capacity=capacity, latency=1, status=status)


@pytest.fixture
def line():
    """A - B - C - D with capacities 10, 3, 7."""
    return Ledger(topology(link("L1", "A", "B", 10), link("L2", "B", "C", 3), link("L3", "C", "D", 7)))


PATH_AB = ["L1:A>B"]
PATH_ABD = ["L1:A>B", "L2:B>D"]


# 3.2 Construction and residual

def test_fresh_ledger_residual_is_capacity():
    ledger = Ledger(topology(link("L1", "A", "B", 10)))
    assert ledger.residual("L1:A>B") == 10
    assert ledger.residual("L1:B>A") == 10


def test_util_cap_reduces_capacity():
    ledger = Ledger(topology(link("L1", "A", "B", 15)), util_cap=0.9)
    assert ledger.residual("L1:A>B") == 13


@pytest.mark.parametrize("capacity, util_cap, expected", [(100, 0.29, 29), (10, 0.7, 7), (10, 1.0, 10)])
def test_effective_capacity_has_no_float_rounding_error(capacity, util_cap, expected):
    assert effective_capacity(capacity, util_cap) == expected


def test_down_arcs_are_excluded():
    ledger = Ledger(topology(link("L1", "A", "B", 10), link("L7", "B", "D", 10, status="down")))
    assert ledger.arcs == ["L1:A>B", "L1:B>A"]
    assert "L7:B>D" not in ledger
    with pytest.raises(KeyError):
        ledger.residual("L7:B>D")


@pytest.mark.parametrize("util_cap", [0, -0.5, 1.5])
def test_util_cap_out_of_range_is_rejected(util_cap):
    with pytest.raises(ValueError):
        Ledger(topology(link("L1", "A", "B", 10)), util_cap=util_cap)


# 3.3 Bottleneck and reserve

def test_bottleneck_is_the_tightest_arc(line):
    assert line.bottleneck(["L1:A>B", "L2:B>C", "L3:C>D"]) == 3


def test_reservation_within_capacity():
    ledger = Ledger(topology(link("L1", "A", "B", 10), link("L2", "B", "D", 10)))
    ledger.reserve(PATH_ABD, 6, cls=0)
    assert ledger.residual("L1:A>B") == 4
    assert ledger.residual("L2:B>D") == 4
    assert ledger.residual("L1:B>A") == 10  # opposite direction untouched


def test_reservation_beyond_capacity_raises_and_changes_nothing():
    ledger = Ledger(topology(link("L1", "A", "B", 10), link("L2", "B", "D", 20)))
    with pytest.raises(CapacityExceeded):
        ledger.reserve(PATH_ABD, 11, cls=0)
    assert ledger.residual("L1:A>B") == 10
    assert ledger.residual("L2:B>D") == 20
    assert ledger.class_breakdown(PATH_ABD) == {}


def test_reserve_on_down_arc_raises():
    ledger = Ledger(topology(link("L1", "A", "B", 10, status="down")))
    with pytest.raises(KeyError):
        ledger.reserve(PATH_AB, 1, cls=0)


@pytest.mark.parametrize("path", [[], ["L1:A>B", "L1:A>B"]])
def test_empty_or_repeating_path_is_rejected(path):
    ledger = Ledger(topology(link("L1", "A", "B", 10)))
    with pytest.raises(ValueError):
        ledger.reserve(path, 1, cls=0)


# 3.4 Release and class breakdown

def test_release_restores_capacity():
    ledger = Ledger(topology(link("L1", "A", "B", 10), link("L2", "B", "D", 10)))
    ledger.reserve(PATH_ABD, 6, cls=1)
    ledger.release(PATH_ABD, 6, cls=1)
    assert all(ledger.residual(a) == ledger.effective(a) for a in ledger.arcs)
    assert ledger.class_breakdown(ledger.arcs) == {}


def test_release_more_than_reserved_raises_and_changes_nothing():
    ledger = Ledger(topology(link("L1", "A", "B", 10)))
    ledger.reserve(PATH_AB, 4, cls=0)
    with pytest.raises(ValueError):
        ledger.release(PATH_AB, 5, cls=0)
    with pytest.raises(ValueError):
        ledger.release(PATH_AB, 4, cls=2)  # wrong class
    assert ledger.residual("L1:A>B") == 6


def test_breakdown_by_class_in_ascending_order():
    ledger = Ledger(topology(link("L1", "A", "B", 20)))
    ledger.reserve(PATH_AB, 5, cls=2)
    ledger.reserve(PATH_AB, 10, cls=0)
    breakdown = ledger.class_breakdown(PATH_AB)
    assert breakdown == {0: 10, 2: 5}
    assert list(breakdown) == [0, 2]
