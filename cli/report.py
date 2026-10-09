"""Results tables and the hypothesis verdicts from a benchmark folder (change add-cli-benchmark, group 4).

`python -m cli report --dir results` reads benchmark.csv and summary.json and writes tables.md and
hypotheses.json next to them. Nothing here runs a policy, so the report can be regenerated from the
files alone. Every interval is the seeded 95% bootstrap interval of `cli.stats`.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from pathlib import Path

from cli.benchmark import ABLATION_LOAD, CASES, LOAD_FACTORS, POLICY_ORDER, read_rows
from cli.hypotheses import Row, Verdict, evaluate, paired_points, per_seed
from cli.stats import summarize

METRICS = (("dr", "DR"), ("dr_p0", "DR_P0"), ("dr_p1", "DR_P1"))


def _present(values: Sequence[float]) -> list[float]:
    return [v for v in values if not math.isnan(v)]


def policy_table(rows: Sequence[Row], case: str) -> str:
    """Mean (and 95% interval) of DR, plus the mean DR_P0 and DR_P1, per load factor and policy, default config."""
    lines = [f"### Case `{case}`", "",
             "| load factor | policy | DR mean [95% CI] | DR median | DR_P0 mean | DR_P1 mean "
             "| overloaded arcs (mean) |",
             "|---|---|---|---|---|---|---|"]
    for load in LOAD_FACTORS:
        for policy in POLICY_ORDER:
            chosen = [r for r in rows if r["case"] == case and r["load_factor"] == load and r["policy"] == policy
                      and r["variant"] == "default"]
            if not chosen:
                continue
            dr = summarize([float(r["dr"]) for r in chosen])
            p0 = _present([float(r["dr_p0"]) for r in chosen])
            p1 = _present([float(r["dr_p1"]) for r in chosen])
            over = sum(int(r["overloaded_arcs"]) for r in chosen) / len(chosen)
            mean_p0 = sum(p0) / len(p0) if p0 else math.nan
            mean_p1 = sum(p1) / len(p1) if p1 else math.nan
            lines.append(f"| {load} | {policy} | {dr.mean:.4f} [{dr.low:.4f}, {dr.high:.4f}] | {dr.median:.4f} | "
                         f"{mean_p0:.4f} | {mean_p1:.4f} | {over:.2f} |")
    return "\n".join(lines)


def paired_table(rows: Sequence[Row]) -> str:
    """S2 minus S0-QoS per seed, in percentage points, per case and load factor."""
    lines = ["| case | load factor | DR difference mean [95% CI] | median | DR_P0 difference | DR_P1 difference |",
             "|---|---|---|---|---|---|"]
    for case in CASES:
        for load in LOAD_FACTORS:
            dr = summarize(paired_points(rows, "dr", (case,), load))
            p0 = summarize(paired_points(rows, "dr_p0", (case,), load))
            p1 = summarize(paired_points(rows, "dr_p1", (case,), load))
            lines.append(f"| {case} | {load} | {dr.mean:+.2f} [{dr.low:+.2f}, {dr.high:+.2f}] | {dr.median:+.2f} | "
                         f"{p0.mean:+.2f} | {p1.mean:+.2f} |")
    return "\n".join(lines)


def ablation_table(rows: Sequence[Row]) -> str:
    """Each S2 variant minus the default S2, per seed, in percentage points, at the ablation load factor."""
    variants = list(dict.fromkeys(r["variant"] for r in rows if r["variant"] != "default"))
    if not variants:
        return "No ablations were run."
    lines = ["| case | variant | DR difference mean [95% CI] | DR_P0 difference | overloaded arcs (mean) |",
             "|---|---|---|---|---|"]
    for case in CASES:
        default = per_seed(rows, "S2", "dr", (case,), ABLATION_LOAD)
        default_p0 = per_seed(rows, "S2", "dr_p0", (case,), ABLATION_LOAD)
        for variant in variants:
            chosen = per_seed(rows, "S2", "dr", (case,), ABLATION_LOAD, variant)
            chosen_p0 = per_seed(rows, "S2", "dr_p0", (case,), ABLATION_LOAD, variant)
            dr = summarize([100 * (chosen[s] - default[s]) for s in sorted(default)])
            p0 = summarize([100 * (chosen_p0[s] - default_p0[s]) for s in sorted(default_p0)])
            over = [int(r["overloaded_arcs"]) for r in rows
                    if r["policy"] == "S2" and r["variant"] == variant and r["case"] == case
                    and r["load_factor"] == ABLATION_LOAD]
            lines.append(f"| {case} | {variant} | {dr.mean:+.2f} [{dr.low:+.2f}, {dr.high:+.2f}] | {p0.mean:+.2f} | "
                         f"{sum(over) / len(over):.2f} |")
    return "\n".join(lines)


def verdict_table(verdicts: Sequence[Verdict]) -> str:
    lines = ["| hypothesis | result | measured |", "|---|---|---|"]
    lines += [f"| {v.id}: {v.statement} | {'passed' if v.passed else 'FAILED'} | {v.measured} |" for v in verdicts]
    return "\n".join(lines)


def tables_markdown(rows: Sequence[Row], summary: dict, verdicts: Sequence[Verdict]) -> str:
    git = summary.get("git", {})
    dirty = " (uncommitted changes)" if git.get("dirty") else ""
    head = [
        "# Benchmark results", "",
        f"{summary.get('seeds_run')} seeds ({', '.join(map(str, summary.get('benchmark_seeds', [])[:3]))}, ...), "
        f"{summary.get('rows')} rows, matrix reduction: {summary.get('reduction')}. "
        f"Code: commit `{str(git.get('commit', 'unknown'))[:10]}`{dirty}.",
        "", "Intervals are 95% bootstrap intervals of the mean over seeds. Differences are S2 minus S0-QoS per seed, "
        "in percentage points.", "",
        "## Hypotheses", "", verdict_table(verdicts), "",
        "## S2 against S0-QoS, per seed", "", paired_table(rows), "",
        "## Ablations of S2 against the default S2 (load factor 1.0)", "", ablation_table(rows), "",
        "## Delivery per policy, case and load factor", "",
    ]
    return "\n".join(head) + "\n" + "\n\n".join(policy_table(rows, c) for c in CASES) + "\n"


def write_report(directory: Path) -> tuple[Path, Path, list[Verdict]]:
    rows = read_rows(directory / "benchmark.csv")
    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    verdicts = evaluate(rows, summary)
    tables = directory / "tables.md"
    hypotheses = directory / "hypotheses.json"
    tables.write_text(tables_markdown(rows, summary, verdicts), encoding="utf-8")
    hypotheses.write_text(json.dumps([{"id": v.id, "statement": v.statement, "passed": v.passed,
                                       "measured": v.measured, "detail": v.detail} for v in verdicts],
                                     indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return tables, hypotheses, verdicts
