"""Tests for the directed arc model (spec: data-model, "Directed arc model")."""

import pytest

from core.model.arcs import Arc, all_arcs, arc_id, available_arcs, link_arcs, parse_arc_id
from core.model.types import Link, Node, Topology


def link(id, u, v, capacity=10, latency=1, status="up"):
    return Link(id=id, u=u, v=v, capacity=capacity, latency=latency, status=status)


def topology(links):
    names = sorted({n for l in links for n in (l.u, l.v)})
    return Topology(nodes=[Node(id=n, type="switch", name=n) for n in names], links=links)


def test_link_expands_to_two_arcs():
    arcs = link_arcs(link("L7", "B", "D", capacity=10))
    assert {a.id for a in arcs} == {"L7:B>D", "L7:D>B"}
    assert all(a.capacity == 10 and a.link == "L7" for a in arcs)


def test_arcs_carry_latency_and_direction():
    forward = next(a for a in link_arcs(link("L2", "A", "B", latency=4)) if a.id == "L2:A>B")
    assert forward == Arc(id="L2:A>B", link="L2", src="A", dst="B", capacity=10, latency=4)


def test_down_link_has_no_available_arcs():
    topo = topology([link("L1", "A", "B"), link("L7", "B", "D", status="down")])
    assert [a.id for a in available_arcs(topo)] == ["L1:A>B", "L1:B>A"]
    assert len(all_arcs(topo)) == 4


def test_arc_order_is_stable_and_sorted():
    topo = topology([link("L9", "C", "D"), link("L10", "A", "C"), link("L2", "A", "B")])
    first = [a.id for a in all_arcs(topo)]
    assert first == [a.id for a in all_arcs(topo)]
    assert first == sorted(first)


def test_arc_order_does_not_depend_on_link_order():
    links = [link("L9", "C", "D"), link("L2", "A", "B")]
    assert all_arcs(topology(links)) == all_arcs(topology(list(reversed(links))))


def test_arc_id_round_trip():
    assert arc_id("L7", "B", "D") == "L7:B>D"
    assert parse_arc_id("L7:B>D") == ("L7", "B", "D")


@pytest.mark.parametrize("bad", ["L7", "L7:BD", ":B>D", "L7:>D", "L7:B>", "L7:B>D>E"])
def test_malformed_arc_id_is_rejected(bad):
    with pytest.raises(ValueError):
        parse_arc_id(bad)


def test_self_loop_is_rejected():
    with pytest.raises(ValueError):
        link_arcs(link("L1", "A", "A"))


def test_node_id_with_separator_is_rejected():
    with pytest.raises(ValueError):
        link_arcs(link("L1", "A>1", "B"))
