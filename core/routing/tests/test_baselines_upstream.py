import pytest

from core.routing.baselines import route_s0, route_s0_qos, upstream_scales
from core.routing.inputs import ArcSpec, FlowSpec
from core.routing.tests.helpers import link, random_case


def chain(cap_ab: int, cap_bc: int) -> list[ArcSpec]:
    return link("L1", "A", "B", cap_ab, 1) + link("L2", "B", "C", cap_bc, 1)


# Hand-worked. Chain A-B (cap 10) and B-C (cap 10); X is A->C 20 Mbps, Y is B->C 10 Mbps.
#   single pass:    A>B scale 10/20, B>C scale 10/30, so X = 20/3 and Y = 10/3.
#   upstream aware: X reaches B>C as 20 * 0.5 = 10, so B>C carries 10 + 10, scale 0.5,
#                   X = 20 * 0.5 * 0.5 = 5 and Y = 10 * 0.5 = 5. Stable from round 3.
S0_FLOWS = [FlowSpec("X", "A", "C", 20, 0), FlowSpec("Y", "B", "C", 10, 0)]


def test_s0_single_pass_is_unchanged_by_default():
    result = route_s0(chain(10, 10), S0_FLOWS)
    assert result.outcomes["X"].delivered == pytest.approx(20 / 3, abs=1e-9)
    assert result.outcomes["Y"].delivered == pytest.approx(10 / 3, abs=1e-9)


def test_s0_upstream_aware_two_link_case():
    result = route_s0(chain(10, 10), S0_FLOWS, upstream_aware=True)
    assert result.outcomes["X"].delivered == pytest.approx(5, abs=1e-9)
    assert result.outcomes["Y"].delivered == pytest.approx(5, abs=1e-9)
    assert result.outcomes["X"].unserved == pytest.approx(15, abs=1e-9)
    assert {o.cause for o in result.outcomes.values()} == {"OVERLOAD_LOSS"}


def test_s0_upstream_aware_converges_in_three_rounds_on_the_two_link_case():
    by_id = {a.id: a for a in chain(10, 10)}
    routes = {"X": ("L1:A>B", "L2:B>C"), "Y": ("L2:B>C",)}
    scales, converged = upstream_scales(by_id, S0_FLOWS, routes, qos=False)
    assert converged
    assert scales == {("L1:A>B", 0): 0.5, ("L2:B>C", 0): 0.5}


# Hand-worked. Chain A-B (cap 6) and B-C (cap 10); X is class 0, A->C 12 Mbps; Y is class 1,
# B->C 4 Mbps.
#   single pass:    B>C class 0 offers 12, so class 1 has max(0, 10 - 12) = 0: X = 12 * 0.5 = 6, Y = 0.
#   upstream aware: X reaches B>C as 12 * 0.5 = 6, leaving 10 - 6 = 4 for class 1, so Y's
#                   scale is 1: X = 12 * 0.5 * 1 = 6 and Y = 4.
QOS_FLOWS = [FlowSpec("X", "A", "C", 12, 0), FlowSpec("Y", "B", "C", 4, 1)]


def test_qos_single_pass_starves_the_lower_class():
    result = route_s0_qos(chain(6, 10), QOS_FLOWS)
    assert result.outcomes["X"].delivered == pytest.approx(6, abs=1e-9)
    assert result.outcomes["Y"].delivered == pytest.approx(0, abs=1e-9)


def test_qos_upstream_aware_gives_the_lower_class_what_the_upstream_loss_frees():
    result = route_s0_qos(chain(6, 10), QOS_FLOWS, upstream_aware=True)
    assert result.outcomes["X"].delivered == pytest.approx(6, abs=1e-9)
    assert result.outcomes["Y"].delivered == pytest.approx(4, abs=1e-9)
    assert (result.outcomes["X"].cause, result.outcomes["Y"].cause) == ("OVERLOAD_LOSS", "NONE")


def test_routes_and_offered_load_are_the_same_in_both_models():
    flows = QOS_FLOWS
    single, upstream = route_s0_qos(chain(6, 10), flows), route_s0_qos(chain(6, 10), flows, upstream_aware=True)
    assert single.arc_load == upstream.arc_load
    for flow_id in single.outcomes:
        assert single.outcomes[flow_id].paths == upstream.outcomes[flow_id].paths


def test_no_overload_changes_nothing():
    flows = [FlowSpec("X", "A", "C", 5, 0)]
    for policy in (route_s0, route_s0_qos):
        outcome = policy(chain(10, 10), flows, upstream_aware=True).outcomes["X"]
        assert (outcome.delivered, outcome.cause) == (5.0, "NONE")


def test_disconnected_and_degenerate_flows():
    flows = [FlowSpec("D", "A", "Z", 5, 0), FlowSpec("S", "A", "A", 7, 0), FlowSpec("Z", "A", "C", 0, 0)]
    outcomes = route_s0(chain(10, 10), flows, upstream_aware=True).outcomes
    assert (outcomes["D"].delivered, outcomes["D"].cause) == (0.0, "DISCONNECTED")
    assert (outcomes["S"].delivered, outcomes["S"].cause) == (7.0, "NONE")
    assert (outcomes["Z"].delivered, outcomes["Z"].cause) == (0.0, "NONE")


def routes_of(arcs, flows):
    outcomes = route_s0(arcs, flows).outcomes
    return {
        f.id: None if outcomes[f.id].cause == "DISCONNECTED" else tuple(a for p in outcomes[f.id].paths for a in p.arcs)
        for f in flows
    }


@pytest.mark.parametrize("seed", range(60))
@pytest.mark.parametrize("qos", [False, True])
def test_random_inputs_converge_and_respect_capacity(seed, qos):
    arcs, flows, _ = random_case(seed)
    by_id = {a.id: a for a in arcs}
    routes = routes_of(arcs, flows)
    scales, converged = upstream_scales(by_id, flows, routes, qos)
    context = f"seed={seed} qos={qos}"
    assert converged, context
    result = (route_s0_qos if qos else route_s0)(arcs, flows, upstream_aware=True)
    carried: dict[str, float] = {}
    for f in flows:
        outcome = result.outcomes[f.id]
        assert 0 <= outcome.delivered <= f.rate + 1e-9, context
        assert outcome.delivered + outcome.unserved == pytest.approx(f.rate, abs=1e-9), context
        rate = float(f.rate)
        for arc_id in routes[f.id] or ():
            rate *= scales[(arc_id, f.cls if qos else 0)]
            carried[arc_id] = carried.get(arc_id, 0.0) + rate
    for arc_id, value in carried.items():
        assert value <= by_id[arc_id].capacity + 1e-6, f"{context} arc={arc_id}"


def test_same_input_same_output_whatever_the_flow_order():
    flows = S0_FLOWS + [FlowSpec("W", "A", "B", 3, 1)]
    for policy in (route_s0, route_s0_qos):
        first = policy(chain(10, 10), flows, upstream_aware=True)
        again = policy(chain(10, 10), list(reversed(flows)), upstream_aware=True)
        assert first.outcomes == again.outcomes
