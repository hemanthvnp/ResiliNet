"""Live mode on core/sim (change add-rest-api, tasks 2.2 to 3.4 and 4.2).

The app runs with check=True, so core's invariant checker runs on every snapshot these tests
receive (task 5.1). Expected numbers are hand-worked by B in fixtures/scenarios/07_diamond.json
and by the team in the PLAN.md section 4 diamond table; none are computed here.
"""

import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from api.app import create_app
from api.live import core_errors
from api.schemas import CompareResponse, RunResponse
from core.model.types import DecisionRecord, Snapshot

ROOT = Path(__file__).resolve().parents[2]
POLICIES = ["S0", "S0-QoS", "S1", "S2"]
DIAMOND = json.loads((ROOT / "fixtures/scenarios/07_diamond.json").read_text())
DELIVERED = DIAMOND["expect"]["delivered"]  # policy -> per step {flow: delivered}
CAMPUS_GEN = {
    "id": "gen", "seed": 3, "events": [], "config": {},
    "topology": {"generator": "campus", "buildings": 12, "redundancy": 0.5, "seed": 3},
    "traffic": {"generator": "campus", "n_flows": 30, "load_factor": 0.5,
                "class_mix": {"0": 0.2, "1": 0.3, "2": 0.5}, "seed": 3},
}


@pytest.fixture(scope="module")
def live():
    return TestClient(create_app(check=True))


def new_run(client, policy="S2", **body):
    res = client.post("/runs", json={"scenario_id": "07_diamond", "policy": policy, **body})
    assert res.status_code == 200, res.text
    return RunResponse.model_validate(res.json())


def event(client, run_id, **body):
    return client.post(f"/runs/{run_id}/events", json=body)


def delivered(snapshot: Snapshot) -> dict[str, float]:
    return {fid: r.delivered for fid, r in sorted(snapshot.allocation.results.items())}


def masked(snapshot: Snapshot) -> Snapshot:
    return snapshot.model_copy(update={"metrics": snapshot.metrics.model_copy(update={"compute_ms": 0.0})})


# --- scenarios (2.2) ---------------------------------------------------------

def test_lists_the_eight_fixture_scenarios_sorted(live):
    body = live.get("/scenarios").json()
    assert [s["id"] for s in body] == [
        "01_normal", "02_uplink_failure", "03_three_links", "04_congestion",
        "05_insufficient_capacity", "06_disconnected", "07_diamond", "08_recovery",
    ]
    assert all(s["name"] and s["description"] for s in body)
    assert "X-Mock" not in live.get("/scenarios").headers


# --- runs (2.3, 3.4) ---------------------------------------------------------

@pytest.mark.parametrize("policy", ["S0", "S0-QoS", "S2"])
def test_diamond_run_at_step0_matches_the_hand_worked_table(live, policy):
    run = new_run(live, policy)
    assert run.snapshot.step == 0
    assert delivered(run.snapshot) == DELIVERED[policy][0]
    assert sorted(l.id for l in run.topology.links) == sorted(run.snapshot.link_state)
    assert [f.id for f in run.flows] == ["F1", "F2"]


@pytest.mark.parametrize("policy", POLICIES)
def test_all_four_policies_create_a_run(live, policy):
    assert new_run(live, policy).snapshot.step == 0


def test_inline_scenario_runs_like_the_builtin(live):
    inline = new_run(live, scenario_id=None, scenario=DIAMOND["scenario"])
    assert masked(inline.snapshot) == masked(new_run(live).snapshot)


def test_unknown_policy_is_422_and_named(live):
    res = live.post("/runs", json={"scenario_id": "07_diamond", "policy": "S9"})
    assert res.status_code == 422 and "S9" in res.json()["detail"]


def test_unknown_scenario_is_404(live):
    assert live.post("/runs", json={"scenario_id": "nope", "policy": "S2"}).status_code == 404


def test_config_is_applied_and_echoed(live):
    run = new_run(live, config={"max_paths": 1})
    assert run.scenario.config.max_paths == 1
    assert all(len(r.paths) <= 1 for r in run.snapshot.allocation.results.values())


# --- generator specs (3.3) ---------------------------------------------------

def test_the_same_generator_request_returns_the_same_topology(live):
    first, second = (new_run(live, scenario_id=None, scenario=CAMPUS_GEN) for _ in range(2))
    assert first.topology == second.topology and first.flows == second.flows
    assert len(first.flows) == 30
    assert first.scenario.topology.seed >= 3  # the effective seed, after any retry


def test_a_bad_generator_parameter_is_422(live):
    bad = {**CAMPUS_GEN, "topology": {**CAMPUS_GEN["topology"], "buildings": 0}}
    res = live.post("/runs", json={"scenario": bad, "policy": "S2"})
    assert res.status_code == 422 and "buildings" in res.json()["detail"]


# --- events and reset (2.4, 4.2) ---------------------------------------------

def test_fail_a_link_reroutes_as_hand_worked(live):
    run = new_run(live)
    snap = Snapshot.model_validate(event(live, run.run_id, kind="fail", links=["L7"]).json())
    assert snap.step == 1 and snap.link_state["L7"] == "down"
    assert delivered(snap) == DELIVERED["S2"][1]


def test_unknown_run_is_404(live):
    assert event(live, "nope", kind="fail", links=["L99"]).status_code == 404


@pytest.mark.parametrize("body", [{"links": ["L99"]}, {"node": "Z"}])
def test_unknown_link_or_node_is_422_and_leaves_the_run_unchanged(live, body):
    run = new_run(live)
    res = event(live, run.run_id, kind="fail", **body)
    assert res.status_code == 422 and ("L99" in res.json()["detail"] or "Z" in res.json()["detail"])
    after = Snapshot.model_validate(event(live, run.run_id, kind="fail", links=[]).json())
    assert after.step == 1 and delivered(after) == delivered(run.snapshot)


def test_failing_a_node_downs_its_links(live):
    run = new_run(live)
    snap = event(live, run.run_id, kind="fail", node="B").json()
    assert {l for l, s in snap["link_state"].items() if s == "down"} == {"L2", "L7"}


def test_repeating_a_failure_changes_nothing_but_the_step(live):
    run = new_run(live)
    once = Snapshot.model_validate(event(live, run.run_id, kind="fail", links=["L7"]).json())
    twice = Snapshot.model_validate(event(live, run.run_id, kind="fail", links=["L7"]).json())
    assert twice.step == 2
    assert (twice.link_state, twice.allocation) == (once.link_state, once.allocation)


def test_reset_equals_step0(live):
    run = new_run(live)
    event(live, run.run_id, kind="fail", links=["L2", "L7"])
    assert masked(Snapshot.model_validate(live.post(f"/runs/{run.run_id}/reset").json())) == masked(run.snapshot)


def test_two_runs_are_isolated(live):
    first, second = new_run(live), new_run(live)
    event(live, first.run_id, kind="fail", links=["L7"])
    assert event(live, second.run_id, kind="fail", links=[]).json()["link_state"]["L7"] == "up"


# --- compare (3.1) -----------------------------------------------------------

def test_compare_on_the_diamond(live):
    res = live.post("/compare", json={"scenario_id": "07_diamond", "policies": POLICIES})
    body = CompareResponse.model_validate(res.json())
    assert [row.policy for row in body.table] == POLICIES
    for row in body.table:
        assert row.metrics == body.snapshots[row.policy][-1].metrics
    assert body.snapshots["S2"][0].metrics.overloaded_arcs == 0
    for policy in ["S0", "S0-QoS", "S2"]:
        assert [delivered(s) for s in body.snapshots[policy]] == DELIVERED[policy]
    link_states = {p: [s.link_state for s in snaps] for p, snaps in body.snapshots.items()}
    assert all(states == link_states["S2"] for states in link_states.values())
    assert [f.id for f in body.flows] == ["F1", "F2"]


def test_compare_on_a_generator_scenario_gives_identical_conditions(live):
    scenario = {**CAMPUS_GEN, "events": [{"step": 1, "kind": "fail", "links": ["L6"]}]}
    body = CompareResponse.model_validate(
        live.post("/compare", json={"scenario": scenario, "policies": ["S0-QoS", "S2"]}).json())
    qos, s2 = body.snapshots["S0-QoS"], body.snapshots["S2"]
    assert len(qos) == len(s2) == 2
    assert [s.link_state for s in qos] == [s.link_state for s in s2]
    assert sorted(qos[0].allocation.results) == sorted(s2[0].allocation.results) == sorted(f.id for f in body.flows)


# --- decisions (3.2) ---------------------------------------------------------

def test_decision_for_the_unserved_s2_flow(live):
    run = new_run(live)
    record = DecisionRecord.model_validate(live.get(f"/runs/{run.run_id}/flows/F2/decision").json())
    assert (record.flow_id, record.step, record.unserved, record.cause) == ("F2", 0, 5, "INSUFFICIENT_CAPACITY")
    assert record.maxflow_bound is not None and record.greedy_gap is not None and record.explanation


def test_decision_follows_the_current_step(live):
    run = new_run(live)
    event(live, run.run_id, kind="fail", links=["L7"])
    record = live.get(f"/runs/{run.run_id}/flows/F1/decision").json()
    assert (record["flow_id"], record["step"]) == ("F1", 1)


def test_decision_for_an_unknown_flow_or_run_is_404(live):
    run = new_run(live)
    assert live.get(f"/runs/{run.run_id}/flows/F99/decision").status_code == 404
    assert live.get("/runs/nope/flows/F1/decision").status_code == 404


# --- error mapping (2.5) -----------------------------------------------------

@pytest.mark.parametrize("err", [ValueError("bad spec"), KeyError("unknown node: Z"),
                                 RuntimeError("no seed from 3 to 22 passes")])
def test_core_input_errors_become_422_with_the_message(err):
    with pytest.raises(HTTPException) as caught:
        with core_errors():
            raise err
    assert caught.value.status_code == 422 and caught.value.detail == err.args[0]


def test_other_errors_stay_500():
    with pytest.raises(ZeroDivisionError):
        with core_errors():
            1 / 0
