"""The seeded benchmark matrix (change add-cli-benchmark, group 3; PLAN.md section 9).

For each benchmark seed one campus network and flow list are built (`cli.cases`), four cases are
derived from them (healthy, uplink, multi, recovered), and every policy runs on identical copies of
each case at each load factor. S2 also runs with each knob changed one at a time. One row per
(seed, case, load factor, policy, variant) holds the configuration and every metric of the final step.

Conditions are identical across policies by construction: the topology, the flows and the failure
set are built once per seed and no policy influences them. The network is resolved once and the
flows are scaled for the load sweep; they are not sent back through the generator's path check,
which would move a heavily loaded network to a different seed.

Output is deterministic apart from `compute_ms`: seeds are a fixed list, every random draw has its
own seeded generator, rows are sorted, and the scheduling of worker processes cannot change a row.
"""

from __future__ import annotations

import csv
import json
import math
import os
import statistics
import subprocess
import sys
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from multiprocessing import Pool
from pathlib import Path
from typing import Literal

from cli.cases import CASES, build_cases
from core.gen.campus import DEFAULT_TOPOLOGY, DEFAULT_TRAFFIC
from core.gen.registry import resolve_topology
from core.gen.traffic import scale_flows
from core.model.types import (
    Cause,
    Event,
    Flow,
    GeneratedTopologySpec,
    GeneratedTrafficSpec,
    PolicyConfig,
    Snapshot,
    Topology,
)
from core.routing.registry import POLICIES
from core.sim.simulation import Simulation

POLICY_ORDER = ("S0", "S0-QoS", "S1", "S2")
LOAD_FACTORS = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0)
ABLATION_LOAD = 1.0  # the ablations run at the demo load, not across the sweep
SEED_STRIDE = 100  # B's note: space benchmark seeds at least 20 apart so a generator retry never lands on another seed
BUDGET_SECONDS = 30 * 60
# Worker processes share one machine, so n of them are not n times faster. Measured on 8 processes: the projection
# without this factor was 118 s and the run took 220 s, an efficiency of 0.54; 0.5 keeps the projection honest.
PARALLEL_EFFICIENCY = 0.5
DEFAULT_SEEDS = 30
CLASSES = (0, 1, 2)
UNSERVED_CAUSES = tuple(c for c in Cause.__args__ if c != "NONE")  # type: ignore[attr-defined]
CONFIG_COLUMNS = ("order", "max_paths", "congestion_lambda", "util_cap")
SCALAR_METRICS = (
    "dr", "dr_reach", "overloaded_arcs", "overload_excess", "max_util", "mean_util", "arcs_above_90",
    "latency_stretch", "recovery_ratio", "churn_flows", "churn_rate", "p0_greedy_gap", "compute_ms",
)
COLUMNS = (
    "seed", "effective_seed", "case", "load_factor", "policy", "variant", *CONFIG_COLUMNS,
    "total_demand", "failed_links",
    *SCALAR_METRICS, *(f"dr_p{c}" for c in CLASSES), *(f"unserved_{c.lower()}" for c in UNSERVED_CAUSES),
)
NOT_REPRODUCIBLE = ("compute_ms",)  # the one column that depends on the machine

# Ablation knobs, in the order they are reported. A lambda is a multiple of the network's mean link latency.
ORDERS: tuple[Literal["arrival", "class_size_asc"], ...] = ("arrival", "class_size_asc")
PATHS = (1, 2, 4)
LAMBDAS = (0.5, 1, 2)
UTIL_CAP = 0.9
ABLATION_GROUPS = ("order", "max_paths", "congestion_lambda", "util_cap")


def benchmark_seed(index: int) -> int:
    """The generator seed of the index-th benchmark seed: 100, 200, 300, ..."""
    return SEED_STRIDE * (index + 1)


def variants(topology: Topology, groups: Sequence[str] = ABLATION_GROUPS) -> list[tuple[str, PolicyConfig]]:
    """The default S2 config, then each changed knob once. The labels do not depend on the network, so
    results group across seeds; the lambda actually used is in the `congestion_lambda` column."""
    mean_latency = statistics.fmean(link.latency for link in topology.links)
    out: list[tuple[str, PolicyConfig]] = [("default", PolicyConfig())]
    if "order" in groups:
        out += [(f"order={o}", PolicyConfig(order=o)) for o in ORDERS]
    if "max_paths" in groups:
        out += [(f"max_paths={m}", PolicyConfig(max_paths=m)) for m in PATHS]
    if "congestion_lambda" in groups:
        out += [(f"lambda={k}xmean", PolicyConfig(congestion_lambda=round(k * mean_latency))) for k in LAMBDAS]
    if "util_cap" in groups:
        out += [(f"util_cap={UTIL_CAP}", PolicyConfig(util_cap=UTIL_CAP))]
    return out


def changed_knobs(a: PolicyConfig, b: PolicyConfig) -> list[str]:
    return [k for k in CONFIG_COLUMNS if getattr(a, k) != getattr(b, k)]


# --- one run -----------------------------------------------------------------------------


def simulate(topology: Topology, flows: list[Flow], events: Sequence[Event], policy: str, cfg: PolicyConfig,
             check: bool = False) -> list[Snapshot]:
    """Step 0 plus one snapshot per event, on this topology and these flows (not resolved again)."""
    simulation = Simulation.from_inputs(topology, flows, policy, cfg, check)
    return [simulation.snapshot] + [simulation.apply(e) for e in sorted(events, key=lambda e: e.step)]


def make_row(seed: int, effective_seed: int, case: str, load: float, policy: str, variant: str, cfg: PolicyConfig,
             flows: list[Flow], snapshot: Snapshot) -> dict:
    metrics = snapshot.metrics
    row: dict = {
        "seed": seed, "effective_seed": effective_seed, "case": case, "load_factor": load, "policy": policy,
        "variant": variant, **{k: getattr(cfg, k) for k in CONFIG_COLUMNS},
        "total_demand": sum(f.rate for f in flows),
        "failed_links": ";".join(sorted(link for link, state in snapshot.link_state.items() if state == "down")),
    }
    for name in SCALAR_METRICS:
        value = getattr(metrics, name)
        row[name] = math.nan if value is None else value  # recovery_ratio is None without a failure
    for c in CLASSES:
        row[f"dr_p{c}"] = metrics.dr_by_class.get(c, math.nan)
    for cause in UNSERVED_CAUSES:
        row[f"unserved_{cause.lower()}"] = metrics.unserved_by_cause.get(cause, 0.0)
    return row


def run_seed(job: tuple[int, dict]) -> list[dict]:
    """All rows of one benchmark seed. `options` is a plain dict so it crosses the process boundary."""
    seed, options = job
    topology_spec = options["topology_spec"]
    cases = build_cases(seed, topology_spec, options["traffic_spec"])
    effective_seed = cases[0].topology.seed  # type: ignore[union-attr]
    topology = resolve_topology(cases[0].topology).topology
    base_flows: list[Flow] = [f for f in cases[0].traffic if isinstance(f, Flow)]
    rows: list[dict] = []
    for scenario in cases:
        case = scenario.id.split("-", 1)[1]
        for load in options["load_factors"]:
            flows = scale_flows(base_flows, load)
            for policy in options["policies"]:
                snapshots = simulate(topology, flows, scenario.events, policy, PolicyConfig(), options["check"])
                rows.append(make_row(seed, effective_seed, case, load, policy, "default", PolicyConfig(), flows,
                                     snapshots[-1]))
            if load == ABLATION_LOAD:
                for label, cfg in variants(topology, options["ablation_groups"])[1:]:
                    snapshots = simulate(topology, flows, scenario.events, "S2", cfg, options["check"])
                    rows.append(make_row(seed, effective_seed, case, load, "S2", label, cfg, flows, snapshots[-1]))
    return rows


def sort_key(row: dict) -> tuple:
    return (row["seed"], CASES.index(row["case"]), row["load_factor"], POLICY_ORDER.index(row["policy"]),
            row["variant"])


# --- sizing the matrix -------------------------------------------------------------------


@dataclass(frozen=True)
class MatrixPlan:
    seeds: int
    ablation_groups: tuple[str, ...]
    projected_seconds: float
    reduction: str  # "" when the full matrix fits the budget


def runs_per_seed(n_loads: int, n_policies: int, ablation_groups: Sequence[str]) -> int:
    per_case = n_loads * n_policies + len(variants_for_count(ablation_groups))
    return len(CASES) * per_case


def variants_for_count(groups: Sequence[str]) -> list[str]:
    return ([f"order={o}" for o in ORDERS] if "order" in groups else []) \
        + ([f"max_paths={m}" for m in PATHS] if "max_paths" in groups else []) \
        + ([f"lambda={k}xmean" for k in LAMBDAS] if "congestion_lambda" in groups else []) \
        + ([f"util_cap={UTIL_CAP}"] if "util_cap" in groups else [])


def plan_matrix(seeds: int, first_seed_seconds: float, processes: int, n_loads: int = len(LOAD_FACTORS),
                n_policies: int = len(POLICY_ORDER), ablations: bool = True,
                budget: float = BUDGET_SECONDS) -> MatrixPlan:
    """Size the matrix from the time of the first seed run with the full matrix (PLAN.md section 9).

    The projection is the first seed's time, scaled by the number of runs and divided by the speed-up of the
    worker processes (n processes at PARALLEL_EFFICIENCY, one process at 1). Over the budget, the ablations shrink
    to max_paths and congestion lambda; still over, to 10 seeds with no ablations (the H12 cut line). The returned
    plan states what was cut."""
    full = ABLATION_GROUPS if ablations else ()
    full_runs = runs_per_seed(n_loads, n_policies, full)

    def projected(count: int, groups: Sequence[str]) -> float:
        speedup = 1.0 if processes <= 1 else processes * PARALLEL_EFFICIENCY
        return first_seed_seconds * count * runs_per_seed(n_loads, n_policies, groups) / full_runs / speedup

    if projected(seeds, full) <= budget:
        return MatrixPlan(seeds, tuple(full), projected(seeds, full), "")
    reduced = ("max_paths", "congestion_lambda") if ablations else ()
    if ablations and projected(seeds, reduced) <= budget:
        return MatrixPlan(seeds, reduced, projected(seeds, reduced),
                          f"projected {projected(seeds, full) / 60:.1f} min for the full matrix, over the "
                          f"{budget / 60:.0f} min budget: ablations cut to max_paths and congestion lambda")
    fewer = min(seeds, 10)
    return MatrixPlan(fewer, (), projected(fewer, ()),
                      f"projected {projected(seeds, full) / 60:.1f} min for the full matrix, over the "
                      f"{budget / 60:.0f} min budget: {fewer} seeds, no ablations")


# --- the benchmark ------------------------------------------------------------------------


@dataclass
class Result:
    rows: list[dict]
    summary: dict = field(default_factory=dict)


def options_for(plan: MatrixPlan, topology_spec: GeneratedTopologySpec, traffic_spec: GeneratedTrafficSpec,
                load_factors: Sequence[float], policies: Sequence[str], check: bool) -> dict:
    return {"topology_spec": topology_spec, "traffic_spec": traffic_spec, "load_factors": tuple(load_factors),
            "policies": tuple(policies), "ablation_groups": plan.ablation_groups, "check": check}


def run_benchmark(seeds: int = DEFAULT_SEEDS, *, processes: int | None = None, ablations: bool = True,
                  load_factors: Sequence[float] = LOAD_FACTORS, policies: Sequence[str] = POLICY_ORDER,
                  topology_spec: GeneratedTopologySpec = DEFAULT_TOPOLOGY,
                  traffic_spec: GeneratedTrafficSpec = DEFAULT_TRAFFIC, check: bool = False,
                  budget: float = BUDGET_SECONDS) -> Result:
    """Run the matrix. The first seed is run in this process with the full matrix and timed; its time sizes the
    rest (see `plan_matrix`). Rows of the first seed that the plan cuts are dropped, not kept."""
    unknown = [p for p in policies if p not in POLICIES]
    if unknown:
        raise ValueError(f"unknown policy {unknown[0]!r}; expected one of {', '.join(sorted(POLICIES))}")
    processes = processes or min(8, os.cpu_count() or 1)
    started = time.perf_counter()
    full_groups = ABLATION_GROUPS if ablations else ()
    full = {"topology_spec": topology_spec, "traffic_spec": traffic_spec, "load_factors": tuple(load_factors),
            "policies": tuple(policies), "ablation_groups": full_groups, "check": check}
    first_start = time.perf_counter()
    first_rows = run_seed((benchmark_seed(0), full))
    first_seconds = time.perf_counter() - first_start
    plan = plan_matrix(seeds, first_seconds, processes, len(load_factors), len(policies), ablations, budget)

    options = options_for(plan, topology_spec, traffic_spec, load_factors, policies, check)
    rows = [r for r in first_rows if r["variant"] == "default" or any(
        r["variant"] in variants_for_count([g]) for g in plan.ablation_groups)]
    rest = [(benchmark_seed(i), options) for i in range(1, plan.seeds)]
    if rest:
        if processes > 1:
            with Pool(processes) as pool:
                for part in pool.imap_unordered(run_seed, rest):
                    rows += part
        else:
            for job in rest:
                rows += run_seed(job)
    rows.sort(key=sort_key)
    summary = {
        "benchmark": "campus generator, 4 policies, 4 cases, load sweep, S2 ablations (PLAN.md section 9)",
        "seeds_requested": seeds, "seeds_run": plan.seeds,
        "benchmark_seeds": [benchmark_seed(i) for i in range(plan.seeds)],
        "seed_stride": SEED_STRIDE, "cases": list(CASES), "policies": list(policies),
        "load_factors": list(load_factors), "ablation_load_factor": ABLATION_LOAD,
        "ablation_groups": list(plan.ablation_groups), "reduction": plan.reduction or "none",
        "topology_spec": topology_spec.model_dump(), "traffic_spec": traffic_spec.model_dump(),
        "rows": len(rows), "processes": processes, "first_seed_seconds": round(first_seconds, 2),
        "projected_seconds": round(plan.projected_seconds, 1), "wall_seconds": round(time.perf_counter() - started, 1),
        "check_invariants": check, "git": git_state(), "python": sys.version.split()[0],
        "not_reproducible_columns": list(NOT_REPRODUCIBLE),
    }
    return Result(rows, summary)


def git_state() -> dict:
    """The commit the numbers came from, and whether the tree had uncommitted changes."""
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], capture_output=True, text=True, check=False,
                              cwd=Path(__file__).resolve().parents[1]).stdout.strip()
    try:
        return {"commit": git("rev-parse", "HEAD") or "unknown", "dirty": bool(git("status", "--porcelain"))}
    except OSError:
        return {"commit": "unknown", "dirty": True}


# --- files --------------------------------------------------------------------------------


def cell(value) -> str:
    if isinstance(value, float):
        return "nan" if math.isnan(value) else repr(value)
    return str(value)


def write_results(result: Result, out: Path) -> tuple[Path, Path]:
    """benchmark.csv (long format, sorted, every column filled) and summary.json."""
    out.mkdir(parents=True, exist_ok=True)
    csv_path, summary_path = out / "benchmark.csv", out / "summary.json"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(COLUMNS)
        for row in result.rows:
            writer.writerow([cell(row[c]) for c in COLUMNS])
    summary_path.write_text(json.dumps(result.summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return csv_path, summary_path


def read_rows(path: Path) -> list[dict]:
    """The rows of a benchmark CSV, with numbers parsed back."""
    text_columns = {"case", "policy", "variant", "order", "failed_links"}
    int_columns = {"seed", "effective_seed", "max_paths", "congestion_lambda", "total_demand", "overloaded_arcs",
                   "overload_excess", "arcs_above_90", "churn_flows", "churn_rate"}
    rows = []
    with path.open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            rows.append({k: (v if k in text_columns else int(v) if k in int_columns else float(v))
                         for k, v in raw.items()})
    return rows


def masked(rows: Iterable[dict]) -> list[dict]:
    """Rows without the columns that depend on the machine, for comparing two runs. A NaN becomes the text
    "nan", because two NaNs from different processes are not equal as floats."""
    return [{k: ("nan" if isinstance(v, float) and math.isnan(v) else v)
             for k, v in r.items() if k not in NOT_REPRODUCIBLE} for r in rows]


def median_compute_ms(repeats: int = 5, *, seed_index: int = 0, case: str = "uplink", load: float = 1.0,
                      policy: str = "S2", topology_spec: GeneratedTopologySpec = DEFAULT_TOPOLOGY,
                      traffic_spec: GeneratedTrafficSpec = DEFAULT_TRAFFIC) -> float:
    """H4 and assumption A3: the median `compute_ms` of the last route call, over fresh runs of one case at demo
    size. The median, not the mean: one slow run on a busy machine must not move it. Run it with nothing else
    going on; the benchmark's own `compute_ms` column is measured with several processes sharing the machine."""
    scenario = next(s for s in build_cases(benchmark_seed(seed_index), topology_spec, traffic_spec)
                    if s.id.endswith(f"-{case}"))
    topology = resolve_topology(scenario.topology).topology
    flows = scale_flows([f for f in scenario.traffic if isinstance(f, Flow)], load)
    times = [simulate(topology, flows, scenario.events, policy, PolicyConfig())[-1].metrics.compute_ms
             for _ in range(repeats)]
    return statistics.median(times)
