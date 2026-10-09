"""Every policy against the frozen fixtures that B wrote by hand (fixtures/, PLAN.md section 7).

The snapshots are the contract: if a policy disagrees with one of them, the policy is wrong or
the contract needs a change that all four members agree on. The fixtures are never edited here.
"""

from pathlib import Path

import pytest
from pydantic import TypeAdapter

from core.model.types import Flow, PolicyConfig, Snapshot, Topology
from core.routing.registry import get_policy

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"


def load_topology() -> Topology:
    return Topology.model_validate_json((FIXTURES / "topologies" / "diamond.json").read_text(encoding="utf-8"))


def load_flows(name: str) -> list[Flow]:
    text = (FIXTURES / "flows" / f"{name}.json").read_text(encoding="utf-8")
    return TypeAdapter(list[Flow]).validate_json(text)


def load_snapshot(name: str) -> Snapshot:
    return Snapshot.model_validate_json((FIXTURES / "snapshots" / f"{name}.json").read_text(encoding="utf-8"))


def assert_same_allocation(got, expected):
    assert got.arc_load == expected.arc_load
    assert set(got.results) == set(expected.results)
    for flow_id, want in expected.results.items():
        have = got.results[flow_id]
        assert have.paths == want.paths, flow_id
        assert have.cause == want.cause, flow_id
        assert have.delivered == pytest.approx(want.delivered, abs=1e-9), flow_id
        assert have.unserved == pytest.approx(want.unserved, abs=1e-9), flow_id


@pytest.mark.parametrize(
    "policy, snapshot",
    [
        ("S0", "diamond_healthy_s0"),
        ("S0-QoS", "diamond_healthy_s0qos"),
        ("S1", "diamond_healthy_s1"),
        ("S2", "diamond_healthy_s2"),
    ],
)
def test_policy_reproduces_the_frozen_diamond_snapshot(policy, snapshot):
    allocation, _ = get_policy(policy).route(load_topology(), load_flows("diamond"), None, PolicyConfig())
    assert_same_allocation(allocation, load_snapshot(snapshot).allocation)


def test_s0_reproduces_the_frozen_fractional_snapshot():
    # 18 and 7 Mbps on one 10 Mbps path: scale 0.4, so 7.2 and 2.8 delivered.
    allocation, _ = get_policy("S0").route(load_topology(), load_flows("s0_fractional"), None, PolicyConfig())
    assert_same_allocation(allocation, load_snapshot("s0_fractional").allocation)


@pytest.mark.parametrize("policy", ["S0", "S0-QoS", "S1", "S2"])
def test_records_cover_every_flow_and_round_trip_through_json(policy):
    from core.model.types import DecisionRecord

    flows = load_flows("diamond")
    _, records = get_policy(policy).route(load_topology(), flows, None, PolicyConfig())
    assert sorted(r.flow_id for r in records) == sorted(f.id for f in flows)
    for record in records:
        assert DecisionRecord.model_validate_json(record.model_dump_json()) == record
