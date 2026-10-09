"""`python -m cli run|compare` (change add-cli-benchmark, tasks 2.1 to 2.4).

Expected numbers are the hand-worked PLAN.md section 4 diamond table and the spec's path-limit
scenario (one path A-B-D of capacity 10 leaves 5 of F1's 15 unserved).
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from api.schemas import CompareResponse
from cli.main import main
from core.model.types import Snapshot

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOTS = TypeAdapter(list[Snapshot])
GENERATED = {
    "id": "gen", "seed": 5, "config": {},
    "topology": {"generator": "campus", "buildings": 12, "redundancy": 0.5, "seed": 5},
    "traffic": {"generator": "campus", "n_flows": 30, "load_factor": 0.5,
                "class_mix": {"0": 0.2, "1": 0.3, "2": 0.5}, "seed": 5},
    "events": [{"step": 1, "kind": "fail", "links": ["L6"]}],
}


def rows(out: str) -> list[list[str]]:
    return [line.split() for line in out.splitlines()[1:]]


def masked(path: Path) -> list:
    data = json.loads(path.read_text())
    for snap in data:
        snap["metrics"]["compute_ms"] = 0.0
    return data


# --- run (2.1) ---------------------------------------------------------------

def test_run_the_diamond_under_s2(tmp_path, capsys):
    out = tmp_path / "run.json"
    assert main(["run", "--scenario", "07_diamond", "--policy", "S2", "--out", str(out)]) == 0
    snapshots = SNAPSHOTS.validate_json(out.read_text())
    assert [s.step for s in snapshots] == [0, 1]
    assert [r[:3] for r in rows(capsys.readouterr().out)] == [["0", "S2", "0.800"], ["1", "S2", "0.400"]]


def test_run_takes_a_scenario_file(tmp_path):
    scenario = tmp_path / "gen.json"
    scenario.write_text(json.dumps(GENERATED))
    assert main(["run", "--scenario", str(scenario), "--policy", "S2"]) == 0


def test_unknown_policy_exits_non_zero_and_names_it(capsys):
    assert main(["run", "--scenario", "07_diamond", "--policy", "S9"]) != 0
    assert "S9" in capsys.readouterr().err


def test_unknown_scenario_exits_non_zero_and_lists_the_ids(capsys):
    assert main(["run", "--scenario", "nope", "--policy", "S2"]) != 0
    assert "07_diamond" in capsys.readouterr().err


# --- compare (2.2) -----------------------------------------------------------

def test_default_compare_on_the_healthy_diamond(capsys):
    assert main(["compare", "--scenario", "07_diamond"]) == 0
    healthy = [r for r in rows(capsys.readouterr().out) if r[0] == "0"]
    assert [r[1] for r in healthy] == ["S0", "S0-QoS", "S1", "S2"]
    s2 = next(r for r in healthy if r[1] == "S2")
    assert (s2[2], s2[6]) == ("0.800", "0")  # DR, overloaded arcs


def test_compare_out_is_the_compare_response_the_frontend_plays_back(tmp_path):
    out = tmp_path / "fallback.json"
    assert main(["compare", "--scenario", "02_uplink_failure", "--policies", "S0-QoS", "S2", "--out", str(out)]) == 0
    body = CompareResponse.model_validate_json(out.read_text())
    assert [row.policy for row in body.table] == ["S0-QoS", "S2"]
    assert len(body.snapshots["S0-QoS"]) == len(body.snapshots["S2"]) == 2
    for row in body.table:
        assert row.metrics == body.snapshots[row.policy][-1].metrics
    assert body.snapshots["S2"][1].link_state["L6"] == "down"


def test_compare_rejects_a_repeated_policy(capsys):
    assert main(["compare", "--scenario", "07_diamond", "--policies", "S2", "S2"]) != 0


# --- config flags (2.3) ------------------------------------------------------

def test_flags_reach_the_echoed_config(tmp_path):
    out = tmp_path / "cmp.json"
    argv = ["compare", "--scenario", "07_diamond", "--policies", "S2", "--order", "arrival",
            "--max-paths", "2", "--lambda", "1", "--util-cap", "0.9", "--out", str(out)]
    assert main(argv) == 0
    cfg = CompareResponse.model_validate_json(out.read_text()).scenario.config
    assert (cfg.order, cfg.max_paths, cfg.congestion_lambda, cfg.util_cap) == ("arrival", 2, 1, 0.9)


# --- reproducibility and purity (2.4) ----------------------------------------

def test_the_same_generator_spec_and_seed_write_identical_output(tmp_path):
    scenario = tmp_path / "gen.json"
    scenario.write_text(json.dumps(GENERATED))
    first, second = tmp_path / "a.json", tmp_path / "b.json"
    for out in (first, second):
        assert main(["run", "--scenario", str(scenario), "--policy", "S2", "--out", str(out)]) == 0
    assert masked(first) == masked(second)


def test_cli_runs_without_importing_the_api():
    code = ("import sys; from cli.main import main; rc = main(['run', '--scenario', '07_diamond', '--policy', 'S2']);"
            "bad = sorted(m for m in sys.modules if m.split('.')[0] in ('api', 'fastapi', 'starlette'));"
            "assert rc == 0 and not bad, bad")
    subprocess.run([sys.executable, "-c", code], cwd=ROOT, check=True, capture_output=True)
