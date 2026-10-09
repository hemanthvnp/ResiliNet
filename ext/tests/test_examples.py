"""Judge kit: the editable scenarios under examples/ (change submission-readiness, tasks 3.1 to 3.3).

Each scenario of specs/judge-kit/spec.md is one test. Runs go through the cycle-1 CLI and
Simulation unchanged, so these tests also show that a judge's edit needs no code change.
"""

import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from cli.main import main
from core.model.types import Snapshot
from core.sim.scenario import load_scenario
from core.sim.simulation import run_scenario

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = sorted((ROOT / "examples").glob("*.json"))
REQUIRED = ["custom-failure.json", "custom-flow.json", "overload.json"]
POLICIES = ["S0", "S0-QoS", "S1", "S2"]


def test_the_required_examples_exist_and_validate():
    assert set(REQUIRED) <= {p.name for p in EXAMPLES}
    for path in EXAMPLES:
        load_scenario(path)


@pytest.mark.parametrize("policy", POLICIES)
@pytest.mark.parametrize("path", [ROOT / "examples" / name for name in REQUIRED], ids=REQUIRED)
def test_every_example_runs_under_every_policy(path, policy):
    assert main(["run", "--scenario", str(path), "--policy", policy]) == 0
    run_scenario(path, policy, check=True)  # raises on any invariant violation; I4 for S1 and S2 only


def test_an_edited_priority_takes_effect(tmp_path):
    scenario = json.loads((ROOT / "examples/custom-flow.json").read_text())
    added = next(f for f in scenario["traffic"] if f["id"] == "F20")
    assert added["cls"] == 0
    added["cls"] = 2
    edited, out = tmp_path / "edited.json", tmp_path / "out.json"
    edited.write_text(json.dumps(scenario))
    assert main(["run", "--scenario", str(edited), "--policy", "S2", "--out", str(out)]) == 0
    [step0] = TypeAdapter(list[Snapshot]).validate_json(out.read_text())
    assert next(d for d in step0.decisions if d.flow_id == "F20").cls == 2


def test_a_mistyped_link_is_rejected_by_name(tmp_path, capsys):
    scenario = json.loads((ROOT / "examples/custom-failure.json").read_text())
    links = scenario["events"][0]["links"]
    links[links.index("L11")] = "L99"
    edited = tmp_path / "edited.json"
    edited.write_text(json.dumps(scenario))
    assert main(["run", "--scenario", str(edited), "--policy", "S2"]) != 0
    assert "L99" in capsys.readouterr().err
