"""S2 ablations on the campus generator (PLAN.md sections 5 and 9; add-routing-policies task 5.1).

Each knob of section 5 is changed one at a time from the default and compared with the default on
the same networks and flows. Criteria fixed before the first run:

- a setting beats the default if the paired mean DR gain is at least 1 percentage point and the 95%
  bootstrap interval is above 0;
- lambda above 0 is kept only if it lowers mean max utilisation by at least 5 points, or beats the
  default on DR by that rule, and raises latency stretch by no more than 10%; otherwise it is removed;
- ordering and max_paths are compared on delivered traffic, fully served flows, compute time and
  paths per flow; util_cap on headroom against delivered traffic.

Run:  python -m core.routing.tests.ablation [seeds] [processes]
Seeds are spaced 100 apart, which is more than the generator's 20-seed retry window.
"""

from __future__ import annotations

import random
import statistics
import sys
import time
from collections.abc import Sequence
from multiprocessing import Pool

from core.gen.campus import DEFAULT_TOPOLOGY, DEFAULT_TRAFFIC
from core.gen.registry import resolve_topology, resolve_traffic
from core.gen.tests.headline import with_link_down
from core.model.arcs import all_arcs
from core.model.types import PolicyConfig
from core.routing.registry import get_policy

SEEDS = list(range(100, 3100, 100))
LOADS = (0.5, 1.0, 1.5)
SCENARIOS = ("healthy", "uplink_failed")
BASE = {"order": "class_size_desc", "max_paths": 3, "congestion_lambda": 0, "util_cap": 1.0}
BOOTSTRAP = 4000


def settings(mean_latency: float) -> dict[str, dict]:
    """The default and every one-knob change, by label."""
    cfgs: dict[str, dict] = {"default": dict(BASE)}
    for order in ("arrival", "class_size_asc"):
        cfgs[f"order={order}"] = {**BASE, "order": order}
    for paths in (1, 2, 4):
        cfgs[f"max_paths={paths}"] = {**BASE, "max_paths": paths}
    for times in (0.5, 1, 2):
        cfgs[f"lambda={times}xmean({round(times * mean_latency)})"] = {
            **BASE,
            "congestion_lambda": round(times * mean_latency),
        }
    cfgs["util_cap=0.9"] = {**BASE, "util_cap": 0.9}
    return cfgs


def measure(topo, flows, kwargs: dict) -> dict[str, float]:
    capacity = {a.id: a.capacity for a in all_arcs(topo)}
    latency = {a.id: a.latency for a in all_arcs(topo)}
    demand = {c: sum(f.rate for f in flows if f.cls == c) for c in (0, 1, 2)}
    start = time.perf_counter()
    alloc, records = get_policy("S2").route(topo, flows, None, PolicyConfig(**kwargs))
    ms = (time.perf_counter() - start) * 1000
    delivered = {c: sum(alloc.results[f.id].delivered for f in flows if f.cls == c) for c in demand}
    utils = [alloc.arc_load[a] / capacity[a] for a in alloc.arc_load if capacity[a]]
    served = [r for r in alloc.results.values() if r.delivered > 0]
    stretch, counted = 0.0, 0
    for r in records:
        if r.delivered > 0 and r.reference_path and r.attempts:
            reference = sum(latency[a] for a in r.reference_path)
            used = sum(a.latency * a.pushed for a in r.attempts) / sum(a.pushed for a in r.attempts)
            if reference:
                stretch += used / reference
                counted += 1
    return {
        "ms": ms,
        "dr": sum(delivered.values()) / sum(demand.values()),
        "dr0": delivered[0] / demand[0],
        "dr1": delivered[1] / demand[1],
        "full": sum(1 for r in alloc.results.values() if r.unserved < 1e-9),
        "paths": sum(len(r.paths) for r in served) / max(1, len(served)),
        "maxutil": max(utils, default=0.0),
        "stretch": stretch / counted if counted else 1.0,
        "gap0": sum((r.greedy_gap or 0) for r in records if r.cls == 0),
    }


def run_seed(job: tuple[int, float]) -> list[dict]:
    seed, load = job
    resolved = resolve_topology(DEFAULT_TOPOLOGY.model_copy(update={"seed": seed}))
    flows = resolve_traffic(DEFAULT_TRAFFIC.model_copy(update={"load_factor": load}), resolved.topology)
    links = resolved.topology.links
    cfgs = settings(sum(link.latency for link in links) / len(links))
    rows = []
    uplink = resolved.primary_uplink
    assert uplink is not None, "the campus generator always names its primary uplink"
    for scenario in SCENARIOS:
        topo = with_link_down(resolved.topology, uplink) if scenario == "uplink_failed" else resolved.topology
        for label, kwargs in cfgs.items():
            rows.append({"seed": seed, "load": load, "scen": scenario, "cfg": label, **measure(topo, flows, kwargs)})
    return rows


def run_all(seeds: Sequence[int], processes: int) -> list[dict]:
    jobs = [(s, load) for s in seeds for load in LOADS]
    with Pool(processes) as pool:
        return [row for part in pool.imap_unordered(run_seed, jobs) for row in part]


def paired(rows_by_key: dict, seeds: Sequence[int], scen: str, load: float, label: str, key: str, scale: float = 1.0):
    """Mean paired difference from the default, with a 95% bootstrap interval."""
    rng = random.Random(0)
    diffs = [(rows_by_key[(scen, load, label, s)][key] - rows_by_key[(scen, load, "default", s)][key]) * scale
             for s in seeds]
    means = sorted(statistics.fmean(rng.choices(diffs, k=len(diffs))) for _ in range(BOOTSTRAP))
    return statistics.fmean(diffs), means[int(0.025 * BOOTSTRAP)], means[int(0.975 * BOOTSTRAP)]


def report(rows: list[dict]) -> str:
    by_key = {(r["scen"], r["load"], r["cfg"], r["seed"]): r for r in rows}
    seeds = sorted({r["seed"] for r in rows})
    labels = list(dict.fromkeys(r["cfg"] for r in rows))
    loads = sorted({r["load"] for r in rows})
    out = [f"{len(seeds)} seeds. Differences from the default; DR in percentage points, 95% bootstrap interval.\n"]
    for scen in SCENARIOS:
        for load in loads:
            base = {k: statistics.fmean(by_key[(scen, load, "default", s)][k] for s in seeds)
                    for k in ("dr", "dr0", "dr1", "maxutil", "stretch", "paths", "ms")}
            out.append(f"{scen}, load factor {load}: default DR {base['dr']:.4f}, DR_P0 {base['dr0']:.4f}, "
                       f"DR_P1 {base['dr1']:.4f}, stretch {base['stretch']:.3f}, paths/flow {base['paths']:.2f}")
            out.append("| setting | dDR [95% CI] | dDR_P0 | dFullyServed | dStretch | dMaxUtil | paths/flow |")
            out.append("|---|---|---|---|---|---|---|")
            for label in labels[1:]:
                dr, lo, hi = paired(by_key, seeds, scen, load, label, "dr", 100)
                dr0 = paired(by_key, seeds, scen, load, label, "dr0", 100)[0]
                full = paired(by_key, seeds, scen, load, label, "full")[0]
                stretch = paired(by_key, seeds, scen, load, label, "stretch", 100)[0]
                util = paired(by_key, seeds, scen, load, label, "maxutil", 100)[0]
                paths = statistics.fmean(by_key[(scen, load, label, s)]["paths"] for s in seeds)
                out.append(f"| {label} | {dr:+.2f} [{lo:+.2f}, {hi:+.2f}] | {dr0:+.2f} | {full:+.1f} | "
                           f"{stretch:+.1f}% | {util:+.1f} | {paths:.2f} |")
            out.append("")
    return "\n".join(out)


def main() -> None:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else len(SEEDS)
    processes = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    started = time.time()
    rows = run_all(SEEDS[:count], processes)
    print(report(rows))
    print(f"{len(rows)} runs in {time.time() - started:.0f} s")


if __name__ == "__main__":
    main()
