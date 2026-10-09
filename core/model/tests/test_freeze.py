"""Contract freeze test (PLAN.md sections 7 and 11; tasks 4.4 and 4.5).

The contract is frozen at H1.5 only when this passes: every section 7 name
imports, and every file under fixtures/ validates against the model its folder
declares. A fixture in an unknown folder fails, so nothing goes unchecked.
"""

import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from core.model import types
from core.sim.scenario import ScenarioFixture

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"

# fixtures/<folder>/*.json -> model each file must validate against
FOLDER_MODELS = {
    "topologies": TypeAdapter(types.Topology),
    "flows": TypeAdapter(list[types.Flow]),
    "snapshots": TypeAdapter(types.Snapshot),
    "decisions": TypeAdapter(types.DecisionRecord),
    "scenarios": TypeAdapter(ScenarioFixture),  # {"scenario": Scenario, "expect": {...}}
}

SECTION_7_NAMES = [
    "Node", "Link", "Topology", "Flow", "PathAlloc", "FlowResult", "Allocation",
    "PolicyConfig", "Event", "Attempt", "CutArc", "DecisionRecord", "Metrics",
    "TopologySpec", "TrafficSpec", "Scenario", "Snapshot", "RoutingPolicy",
]

# The freeze needs a fixture for the diamond under every policy, the fractional
# S0 case and the section 10 record (PLAN.md section 7, "the freeze is valid only if").
REQUIRED = [
    "topologies/diamond.json",
    "flows/diamond.json",
    "snapshots/diamond_healthy_s0.json",
    "snapshots/diamond_healthy_s0qos.json",
    "snapshots/diamond_healthy_s1.json",
    "snapshots/diamond_healthy_s2.json",
    "snapshots/s0_fractional.json",
    "decisions/section10_f12.json",
]


def fixture_files():
    return sorted(p for p in FIXTURES.rglob("*") if p.is_file())


@pytest.mark.parametrize("name", SECTION_7_NAMES)
def test_section_7_name_imports(name):
    assert getattr(types, name) is not None


@pytest.mark.parametrize("path", fixture_files(), ids=lambda p: p.relative_to(FIXTURES).as_posix())
def test_fixture_validates_against_its_model(path):
    rel = path.relative_to(FIXTURES)
    assert path.suffix == ".json", f"{rel}: fixtures are JSON files"
    assert len(rel.parts) == 2 and rel.parts[0] in FOLDER_MODELS, (
        f"{rel}: put fixtures in one of {sorted(FOLDER_MODELS)}"
    )
    FOLDER_MODELS[rel.parts[0]].validate_json(path.read_bytes())


@pytest.mark.parametrize("rel", REQUIRED)
def test_required_fixture_exists(rel):
    assert (FIXTURES / rel).is_file()


def test_section_10_decision_record():
    raw = (FIXTURES / "decisions" / "section10_f12.json").read_text(encoding="utf-8")
    record = types.DecisionRecord.model_validate_json(raw)
    assert record.cut[0].load_by_class == {0: 10}
    assert record.cut[1].load_by_class == {}
    assert record.delivered == 10.0 and record.unserved == 5.0
    # A round trip through JSON gives the same record.
    assert types.DecisionRecord.model_validate(json.loads(record.model_dump_json())) == record
