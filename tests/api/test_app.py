"""API skeleton, mock mode and the OpenAPI contract (change add-rest-api, tasks 1.2 to 1.5 and 4.1)."""

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from api.export_openapi import SCHEMA_FILE, generated
from api.schemas import CompareResponse, RunResponse
from core.model.types import DecisionRecord, Snapshot

ROOT = Path(__file__).resolve().parents[2]
POLICIES = ["S0", "S0-QoS", "S1", "S2"]
ROUTES = {
    ("GET", "/scenarios"),
    ("POST", "/runs"),
    ("POST", "/runs/{run_id}/events"),
    ("POST", "/runs/{run_id}/reset"),
    ("POST", "/compare"),
    ("GET", "/runs/{run_id}/flows/{flow_id}/decision"),
}


@pytest.fixture
def mock():
    return TestClient(create_app(mock=True))


def fixture_snapshot(policy):
    name = {"S0": "s0", "S0-QoS": "s0qos", "S1": "s1", "S2": "s2"}[policy]
    return Snapshot.model_validate_json((ROOT / f"fixtures/snapshots/diamond_healthy_{name}.json").read_text())


def new_run(client, policy="S2"):
    res = client.post("/runs", json={"scenario_id": "diamond", "policy": policy})
    assert res.status_code == 200, res.text
    return res.json()


# --- skeleton (1.2, 1.3) -------------------------------------------------------

def test_app_starts():
    assert TestClient(create_app()).get("/openapi.json").status_code == 200


def test_all_six_routes_are_registered():
    app = create_app()
    registered = {(m, r.path) for r in app.routes for m in getattr(r, "methods", ()) if m != "HEAD"}
    assert ROUTES <= registered


def test_live_mode_answers_501_until_the_simulation_lands():
    res = TestClient(create_app()).get("/scenarios")
    assert res.status_code == 501
    assert "REROUTER_MOCK=1" in res.json()["detail"]


# --- mock mode (1.4) -----------------------------------------------------------

def test_mock_responses_are_marked(mock):
    assert mock.get("/scenarios").headers["X-Mock"] == "true"


def test_mock_lists_the_diamond(mock):
    assert [s["id"] for s in mock.get("/scenarios").json()] == ["diamond"]


@pytest.mark.parametrize("policy", POLICIES)
def test_mock_run_returns_the_step0_fixture_for_its_policy(mock, policy):
    body = RunResponse.model_validate(new_run(mock, policy))
    assert body.snapshot == fixture_snapshot(policy)
    assert body.snapshot.step == 0
    assert sorted(l.id for l in body.topology.links) == sorted(body.snapshot.link_state)
    assert [f.id for f in body.flows] == ["F1", "F2"]


def test_unknown_policy_is_422_and_named(mock):
    res = mock.post("/runs", json={"scenario_id": "diamond", "policy": "S9"})
    assert res.status_code == 422
    assert "S9" in res.json()["detail"]


def test_unknown_scenario_is_404(mock):
    assert mock.post("/runs", json={"scenario_id": "nope", "policy": "S2"}).status_code == 404


@pytest.mark.parametrize("body", [{"policy": "S2"}, {"scenario_id": "diamond", "scenario": {}, "policy": "S2"}])
def test_scenario_id_and_scenario_are_exclusive(mock, body):
    assert mock.post("/runs", json=body).status_code == 422


def test_unknown_request_field_is_rejected(mock):
    assert mock.post("/runs", json={"scenario_id": "diamond", "policy": "S2", "seed": 1}).status_code == 422


def test_fail_a_link(mock):
    run = new_run(mock)
    snap = Snapshot.model_validate(mock.post(f"/runs/{run['run_id']}/events", json={"kind": "fail", "links": ["L7"]}).json())
    assert snap.step == 1
    assert snap.link_state == {"L2": "up", "L5": "up", "L6": "up", "L7": "down"}


def test_fail_a_node_downs_its_links(mock):
    run = new_run(mock)
    snap = mock.post(f"/runs/{run['run_id']}/events", json={"kind": "fail", "node": "B"}).json()
    assert snap["link_state"] == {"L2": "down", "L5": "up", "L6": "up", "L7": "down"}


def test_recover_brings_a_link_back(mock):
    run_id = new_run(mock)["run_id"]
    mock.post(f"/runs/{run_id}/events", json={"kind": "fail", "links": ["L7"]})
    snap = mock.post(f"/runs/{run_id}/events", json={"kind": "recover", "links": ["L7"]}).json()
    assert (snap["step"], snap["link_state"]["L7"]) == (2, "up")


def test_unknown_link_is_422_and_leaves_the_run_unchanged(mock):
    run_id = new_run(mock)["run_id"]
    res = mock.post(f"/runs/{run_id}/events", json={"kind": "fail", "links": ["L99"]})
    assert res.status_code == 422 and "L99" in res.json()["detail"]
    snap = mock.post(f"/runs/{run_id}/events", json={"kind": "fail", "links": []}).json()
    assert snap["step"] == 1 and set(snap["link_state"].values()) == {"up"}


def test_event_on_unknown_run_is_404(mock):
    assert mock.post("/runs/nope/events", json={"kind": "fail", "links": ["L7"]}).status_code == 404


def test_reset_returns_the_original_step0(mock):
    run = new_run(mock, "S0-QoS")
    mock.post(f"/runs/{run['run_id']}/events", json={"kind": "fail", "links": ["L2", "L7"]})
    assert Snapshot.model_validate(mock.post(f"/runs/{run['run_id']}/reset").json()) == fixture_snapshot("S0-QoS")


def test_two_runs_are_isolated(mock):
    first, second = new_run(mock)["run_id"], new_run(mock)["run_id"]
    assert first != second
    mock.post(f"/runs/{first}/events", json={"kind": "fail", "links": ["L7"]})
    snap = mock.post(f"/runs/{second}/events", json={"kind": "fail", "links": []}).json()
    assert snap["link_state"]["L7"] == "up"


def test_compare_has_one_row_per_policy_in_request_order(mock):
    res = mock.post("/compare", json={"scenario_id": "diamond", "policies": POLICIES})
    body = CompareResponse.model_validate(res.json())
    assert [row.policy for row in body.table] == POLICIES
    assert sorted(body.snapshots) == sorted(POLICIES)
    assert next(r for r in body.table if r.policy == "S2").metrics.overloaded_arcs == 0


def test_compare_carries_topology_and_flows_for_offline_rendering(mock):
    body = CompareResponse.model_validate(mock.post("/compare", json={"scenario_id": "diamond", "policies": ["S2"]}).json())
    assert sorted(l.id for l in body.topology.links) == ["L2", "L5", "L6", "L7"]
    assert [f.id for f in body.flows] == ["F1", "F2"]


def test_decision_for_a_known_flow_validates(mock):
    run_id = new_run(mock)["run_id"]
    DecisionRecord.model_validate(mock.get(f"/runs/{run_id}/flows/F1/decision").json())


def test_decision_for_an_unknown_flow_or_run_is_404(mock):
    run_id = new_run(mock)["run_id"]
    assert mock.get(f"/runs/{run_id}/flows/F99/decision").status_code == 404
    assert mock.get("/runs/nope/flows/F1/decision").status_code == 404


# --- contract (1.5) and purity (4.1) -------------------------------------------

def test_committed_openapi_schema_is_current():
    assert json.loads(SCHEMA_FILE.read_text(encoding="utf-8")) == generated(), (
        "api/openapi.json is stale; run `python -m api.export_openapi` (a schema change needs all four members)"
    )


def test_core_does_not_import_the_web_layer():
    pattern = re.compile(r"^\s*(from|import)\s+(fastapi|starlette|api)\b", re.MULTILINE)
    offenders = [p for p in (ROOT / "core").rglob("*.py") if pattern.search(p.read_text(encoding="utf-8"))]
    assert offenders == []
