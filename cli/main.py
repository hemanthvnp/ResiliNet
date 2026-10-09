"""`python -m cli run|compare` (change add-cli-benchmark, tasks 2.1 to 2.4; design: "Three subcommands on one entry point").

    run      --scenario <file|id> --policy <name> [--out file]    snapshot sequence as JSON
    compare  --scenario <file|id> [--policies ...] [--out file]   the /compare body as JSON

Both print the headline metrics per step. A scenario is a JSON file (a Scenario or a scenario
fixture) or the id of a fixture under fixtures/scenarios/. The CLI runs core directly and never
imports the API, so it works with no server. `compare --out` writes the same body as
`POST /compare`, which the frontend plays back offline.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from core.gen.registry import resolve_inputs
from core.model.types import GeneratedTopologySpec, PolicyConfig, Scenario, Snapshot
from core.sim.scenario import load_fixture, load_scenario
from core.sim.simulation import Simulation

SCENARIO_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "scenarios"
DEFAULT_POLICIES = ["S0", "S0-QoS", "S1", "S2"]
HEADER = f"{'step':>4}  {'policy':<7} {'DR':>6} {'DR_P0':>6} {'DR_P1':>6} {'DR_P2':>6} {'overloaded':>10} {'max_util':>8}"


def load(source: str) -> Scenario:
    """A scenario file, else a fixture id."""
    if Path(source).is_file():
        return load_scenario(source)
    for path in sorted(SCENARIO_DIR.glob("*.json")):
        scenario = load_fixture(path).scenario
        if scenario.id == source:
            return scenario
    ids = sorted(load_fixture(p).scenario.id for p in SCENARIO_DIR.glob("*.json"))
    raise ValueError(f"no scenario file or id {source!r}; built-in ids: {', '.join(ids)}")


def config(args: argparse.Namespace, scenario: Scenario) -> PolicyConfig:
    flags = {"order": args.order, "max_paths": args.max_paths,
             "congestion_lambda": args.congestion_lambda, "util_cap": args.util_cap}
    return PolicyConfig.model_validate({**scenario.config.model_dump(),
                                        **{k: v for k, v in flags.items() if v is not None}})


def simulate(scenario: Scenario, policy: str, cfg: PolicyConfig) -> tuple[Simulation, list[Snapshot]]:
    """Step 0, then one snapshot per scenario event in step order, on a deep copy of the scenario."""
    sim = Simulation(scenario, policy, cfg)
    events = sorted(sim.scenario.events, key=lambda e: e.step)
    return sim, [sim.snapshot] + [sim.apply(e) for e in events]


def effective(scenario: Scenario, cfg: PolicyConfig, seed: int | None) -> Scenario:
    """The scenario as run: the config used, and the generator seed after any retry."""
    update = {"config": cfg}
    if isinstance(scenario.topology, GeneratedTopologySpec):
        update["topology"] = scenario.topology.model_copy(update={"seed": seed})
    return scenario.model_copy(update=update)


def row(policy: str, snap: Snapshot) -> str:
    by_class = [snap.metrics.dr_by_class.get(c) for c in (0, 1, 2)]
    cells = " ".join(f"{v:>6.3f}" if v is not None else f"{'-':>6}" for v in by_class)
    return (f"{snap.step:>4}  {policy:<7} {snap.metrics.dr:>6.3f} {cells} "
            f"{snap.metrics.overloaded_arcs:>10} {snap.metrics.max_util:>8.3f}")


def write(path: str | None, data) -> None:
    if path:
        Path(path).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def cmd_run(args: argparse.Namespace) -> None:
    scenario = load(args.scenario)
    _, snapshots = simulate(scenario, args.policy, config(args, scenario))
    print(HEADER)
    for snap in snapshots:
        print(row(args.policy, snap))
    write(args.out, [s.model_dump(mode="json") for s in snapshots])


def cmd_compare(args: argparse.Namespace) -> None:
    scenario = load(args.scenario)
    cfg = config(args, scenario)
    if len(set(args.policies)) != len(args.policies):
        raise ValueError(f"repeated policy in {args.policies}")
    runs = {p: simulate(scenario, p, cfg)[1] for p in args.policies}
    print(HEADER)
    for step in range(len(next(iter(runs.values())))):
        for policy in args.policies:
            print(row(policy, runs[policy][step]))
    if args.out:
        resolved, flows = resolve_inputs(scenario.topology, scenario.traffic)
        write(args.out, {
            "scenario": effective(scenario, cfg, resolved.seed).model_dump(mode="json"),
            "topology": resolved.topology.model_dump(mode="json"),
            "flows": [f.model_dump(mode="json") for f in flows],
            "table": [{"policy": p, "metrics": runs[p][-1].metrics.model_dump(mode="json")} for p in args.policies],
            "snapshots": {p: [s.model_dump(mode="json") for s in runs[p]] for p in args.policies},
        })


def cmd_benchmark(args: argparse.Namespace) -> None:
    from cli.benchmark import run_benchmark, write_results
    from core.gen.campus import DEFAULT_TOPOLOGY, DEFAULT_TRAFFIC

    topology = DEFAULT_TOPOLOGY if args.buildings is None else DEFAULT_TOPOLOGY.model_copy(
        update={"buildings": args.buildings})
    traffic = DEFAULT_TRAFFIC if args.flows is None else DEFAULT_TRAFFIC.model_copy(update={"n_flows": args.flows})
    result = run_benchmark(args.seeds, processes=args.processes, ablations=not args.no_ablations,
                           topology_spec=topology, traffic_spec=traffic, check=args.check)
    csv_path, summary_path = write_results(result, Path(args.out))
    s = result.summary
    print(f"{s['rows']} rows for {s['seeds_run']} seeds in {s['wall_seconds']} s "
          f"(first seed {s['first_seed_seconds']} s, projected {s['projected_seconds']} s, {s['processes']} processes)")
    if s["reduction"] != "none":
        print(f"matrix reduced: {s['reduction']}")
    print(f"wrote {csv_path} and {summary_path}")


def parser() -> argparse.ArgumentParser:
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--scenario", required=True, help="scenario JSON file or built-in id, e.g. 07_diamond")
    shared.add_argument("--out", help="write JSON here")
    shared.add_argument("--order", choices=["arrival", "class_size_desc", "class_size_asc"])
    shared.add_argument("--max-paths", type=int)
    shared.add_argument("--lambda", dest="congestion_lambda", type=int, help="congestion lambda")
    shared.add_argument("--util-cap", type=float)

    top = argparse.ArgumentParser(prog="python -m cli", description="Network Rerouter command line")
    sub = top.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", parents=[shared], help="run one policy, write the snapshot sequence")
    run.add_argument("--policy", required=True)
    run.set_defaults(func=cmd_run)
    compare = sub.add_parser("compare", parents=[shared], help="run several policies on one scenario")
    compare.add_argument("--policies", nargs="+", default=DEFAULT_POLICIES)
    compare.set_defaults(func=cmd_compare)
    bench = sub.add_parser("benchmark", help="run the seeded benchmark matrix, write the CSV and a summary")
    bench.add_argument("--seeds", type=int, default=30, help="number of benchmark seeds (default 30)")
    bench.add_argument("--out", default="results", help="output folder (default results/)")
    bench.add_argument("--no-ablations", action="store_true", help="skip the one-knob S2 ablations")
    bench.add_argument("--processes", type=int, help="worker processes (default: up to 8)")
    bench.add_argument("--buildings", type=int, help="campus size in buildings (default 37, about 50 nodes)")
    bench.add_argument("--flows", type=int, help="number of flows (default 200)")
    bench.add_argument("--check", action="store_true", help="assert the invariants on every snapshot (slower)")
    bench.set_defaults(func=cmd_benchmark)
    return top


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        args.func(args)
    except (ValueError, KeyError, RuntimeError) as err:  # bad input from the user, reported by core
        print(f"error: {err.args[0] if err.args else err}", file=sys.stderr)
        return 1
    return 0
