"""Tests for the shared contract (spec: data-model; PLAN.md section 7)."""

import typing

import pytest
from pydantic import BaseModel, ValidationError

from core.model import types
from core.model.types import (
    CutArc,
    Event,
    Flow,
    FlowResult,
    Link,
    PolicyConfig,
    Topology,
)

CONTRACT_MODELS = [
    "Node", "Link", "Topology", "Flow", "PathAlloc", "FlowResult", "Allocation",
    "PolicyConfig", "Event", "Attempt", "CutArc", "DecisionRecord", "Metrics",
    "Scenario", "Snapshot",
]
CONTRACT_ALIASES = ["TopologySpec", "TrafficSpec"]


def link(**overrides):
    fields = dict(id="L7", u="B", v="D", capacity=10, latency=1, status="up")
    fields.update(overrides)
    return Link(**fields)


def flow(**overrides):
    fields = dict(id="F1", src="A", dst="D", rate=15, cls=0)
    fields.update(overrides)
    return Flow(**fields)


def result(**overrides):
    fields = dict(flow_id="F1", paths=[], delivered=0.0, unserved=0.0, cause="NONE")
    fields.update(overrides)
    return FlowResult(**fields)


# 2.1 Network and traffic

def test_link_rejects_non_integer_capacity():
    with pytest.raises(ValidationError):
        link(capacity=10.5)


def test_link_rejects_non_integer_latency():
    with pytest.raises(ValidationError):
        link(latency=1.5)


def test_link_rejects_unknown_status():
    with pytest.raises(ValidationError):
        link(status="degraded")


def diamond_topology(nodes=("A", "B", "C", "D"), link_ids=("L2", "L7", "L5", "L6")):
    ends = [("A", "B"), ("B", "D"), ("A", "C"), ("C", "D")]
    return dict(
        nodes=[dict(id=n, type="switch", name=n) for n in nodes],
        links=[dict(id=i, u=u, v=v, capacity=10, latency=1, status="up")
               for i, (u, v) in zip(link_ids, ends)],
    )


def test_topology_accepts_consistent_ids():
    Topology(**diamond_topology())


def test_topology_rejects_duplicate_node_id():
    with pytest.raises(ValidationError, match="duplicate node id"):
        Topology(**diamond_topology(nodes=("A", "B", "C", "D", "A")))


def test_topology_rejects_duplicate_link_id():
    with pytest.raises(ValidationError, match="duplicate link id"):
        Topology(**diamond_topology(link_ids=("L1", "L1", "L5", "L6")))


def test_topology_rejects_link_to_unknown_node():
    with pytest.raises(ValidationError, match="unknown node"):
        Topology(**diamond_topology(nodes=("A", "B", "C")))


def test_flow_rejects_non_integer_rate():
    with pytest.raises(ValidationError):
        flow(rate=7.5)


def test_flow_service_defaults_to_empty():
    assert flow().service == ""


def test_unknown_field_is_rejected():
    with pytest.raises(ValidationError):
        flow(colour="red")


# 2.2 Allocation

def test_fractional_delivery_is_preserved():
    r = result(delivered=2.8, unserved=4.2, cause="OVERLOAD_LOSS")
    assert r.delivered == 2.8
    assert r.unserved == 4.2


def test_unknown_cause_is_rejected():
    with pytest.raises(ValidationError):
        result(cause="CONGESTION")


@pytest.mark.parametrize(
    "cause", ["NONE", "DISCONNECTED", "INSUFFICIENT_CAPACITY", "PATH_LIMIT", "OVERLOAD_LOSS"]
)
def test_every_listed_cause_is_accepted(cause):
    assert result(cause=cause).cause == cause


# 2.3 Config and events

def test_policy_config_defaults():
    cfg = PolicyConfig()
    assert cfg.order == "class_size_desc"
    assert cfg.max_paths == 3
    assert cfg.congestion_lambda == 0
    assert cfg.util_cap == 1.0


def test_event_defaults():
    e = Event(step=1, kind="fail")
    assert e.links == []
    assert e.node is None


def test_event_rejects_unknown_kind():
    with pytest.raises(ValidationError):
        Event(step=1, kind="degrade")


# 2.4 Decision records

def test_load_by_class_string_keys_load_as_int():
    cut = CutArc.model_validate_json('{"arc": "L5:A>C", "state": "saturated", "load_by_class": {"0": 10}}')
    assert cut.load_by_class == {0: 10}


# 2.5 Every contract name exists and no field is Any

@pytest.mark.parametrize("name", CONTRACT_MODELS + CONTRACT_ALIASES + ["RoutingPolicy"])
def test_contract_name_is_importable(name):
    assert hasattr(types, name)


def _mentions_any(annotation) -> bool:
    if annotation is typing.Any:
        return True
    return any(_mentions_any(arg) for arg in typing.get_args(annotation))


def _all_models():
    return [obj for obj in vars(types).values()
            if isinstance(obj, type) and issubclass(obj, BaseModel) and obj.__module__ == types.__name__]


@pytest.mark.parametrize("model", _all_models(), ids=lambda m: m.__name__)
def test_no_field_is_typed_any(model):
    for name, field in model.model_fields.items():
        assert not _mentions_any(field.annotation), f"{model.__name__}.{name} is typed Any"
