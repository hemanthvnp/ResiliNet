"""`python -m ext run|compare|sweep` (changes ecmp-baseline and criticality-sweep).

    run, compare   the cycle-1 commands, unchanged, with ECMP and ECMP-QoS registered
    sweep --scenario <file|id> [--policies ...] [--out file.csv] [--check]

Scenarios load through the cycle-1 CLI loader, so a fixture id or a scenario file works.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import ext
from cli.main import load
from cli.main import main as cli_main
from core.routing.registry import POLICIES
from core.sim.simulation import Simulation
from ext.sweep import summary, sweep, to_csv


def default_policies() -> list[str]:
    return ["S2", "S0-QoS"] + (["ECMP-QoS"] if "ECMP-QoS" in POLICIES else [])


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(prog="python -m ext", description="Network Rerouter cycle 2 commands; "
                                  "`run` and `compare` are the cycle-1 commands with ECMP and ECMP-QoS added")
    sub = top.add_subparsers(dest="command", required=True)
    s = sub.add_parser("sweep", help="fail each link alone and rank the damage, per policy")
    s.add_argument("--scenario", required=True, help="scenario JSON file or built-in id, e.g. 01_normal")
    s.add_argument("--policies", nargs="+", help="default: S2 and S0-QoS, plus ECMP-QoS if registered")
    s.add_argument("--out", help="write the CSV here")
    s.add_argument("--check", action="store_true", help="assert the invariants on every snapshot (slower)")
    return top


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    ext.register()
    if argv[:1] in (["run"], ["compare"]):
        return cli_main(argv)
    args = parser().parse_args(argv)
    try:
        scenario = load(args.scenario)
        rows = sweep(lambda p: Simulation(scenario, p, check=args.check), args.policies or default_policies())
    except (ValueError, KeyError, RuntimeError) as err:  # bad input, reported by core
        print(f"error: {err.args[0] if err.args else err}", file=sys.stderr)
        return 1
    print(summary(rows))
    if args.out:
        Path(args.out).write_text(to_csv(rows), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
