import pytest

from core.model.types import PolicyConfig
from core.routing.registry import POLICIES, S0QoS, get_policy
from core.routing.tests.helpers import F1, F2, diamond, node_paths, run


def route(name, links, flows, cfg=None, **kwargs):
    return run(get_policy(name).route, links, flows, cfg, **kwargs)


def test_lookup_by_name():
    assert sorted(POLICIES) == ["S0", "S0-QoS", "S1", "S2"]
    assert isinstance(get_policy("S0-QoS"), S0QoS)


def test_every_policy_has_its_name_and_a_route_method():
    for name, policy in POLICIES.items():
        assert policy.name == name
        assert callable(policy.route)


def test_unknown_name_raises():
    with pytest.raises(ValueError, match="unknown policy"):
        get_policy("S3")


@pytest.mark.parametrize("name", ["S0", "S0-QoS", "S1", "S2"])
def test_repeat_run_gives_equal_allocation(name):
    assert route(name, diamond(), [F1, F2]).allocation == route(name, diamond(), [F1, F2]).allocation


def test_s1_never_splits_and_places_in_arrival_order():
    result = route("S1", diamond(), [F2, F1])  # P2 first in the input
    assert all(len(o.paths) <= 1 for o in result.outcomes.values())
    assert list(result.outcomes) == ["F2", "F1"]
    # F2 (10) fills A-B-D; F1 (15) is forced onto A-C-D and fills it. No path has residual
    # left, so the 5 unserved are INSUFFICIENT_CAPACITY, not PATH_LIMIT.
    assert node_paths(result.outcomes["F2"]) == [["A", "B", "D"]]
    assert node_paths(result.outcomes["F1"]) == [["A", "C", "D"]]
    assert result.outcomes["F1"].delivered == 10 and result.outcomes["F1"].cause == "INSUFFICIENT_CAPACITY"


def test_s1_ignores_order_knobs_in_the_config():
    cfg = PolicyConfig(order="class_size_desc", max_paths=3, congestion_lambda=5)
    result = route("S1", diamond(), [F2, F1], cfg)
    assert list(result.outcomes) == ["F2", "F1"] and all(len(o.paths) <= 1 for o in result.outcomes.values())


def test_s2_uses_the_config_as_given():
    result = route("S2", diamond(), [F2, F1], PolicyConfig(order="arrival"))
    assert list(result.outcomes) == ["F2", "F1"]


def test_s1_limits_a_flow_to_one_path_even_when_a_second_would_fit():
    # F1 alone on the healthy diamond: S2 splits 10 + 5, S1 stops after the first path.
    s1 = route("S1", diamond(), [F1]).outcomes["F1"]
    s2 = route("S2", diamond(), [F1]).outcomes["F1"]
    assert (len(s1.paths), s1.delivered, s1.cause) == (1, 10.0, "PATH_LIMIT")
    assert (len(s2.paths), s2.delivered, s2.cause) == (2, 15.0, "NONE")


def test_the_config_is_not_changed_by_s1():
    cfg = PolicyConfig(order="class_size_desc", max_paths=3, congestion_lambda=5)
    route("S1", diamond(), [F1], cfg)
    assert cfg == PolicyConfig(order="class_size_desc", max_paths=3, congestion_lambda=5)


def test_step_is_written_into_the_records():
    result = route("S2", diamond(), [F1], step=4)
    assert [r.step for r in result.records] == [4]
