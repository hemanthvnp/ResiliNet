"""Hypotheses H1 to H5 of PLAN.md section 9, evaluated against S0-QoS on the benchmark rows
(change add-cli-benchmark, task 4.4). A failed hypothesis is reported, never left out.

How each one is read on the benchmark matrix. These readings were fixed before the benchmark rows
were examined for the hypothesis in question, and are repeated in the README:

* Stress cases are `uplink` (like fixture scenario 2) and `multi` (like 3), at load factor 1.0, the
  generated traffic as it is. The per-seed quantity is the mean over those two cases.
* Uncongested cases are `healthy` (scenario 1) and `recovered` (scenario 8). The generated campus
  network is already congested under shortest-path routing at load factor 1.0, so "uncongested" is
  read at the lowest factor, 0.5. This reading was chosen after seeing that healthy S0-QoS delivery
  at load 1.0 is below S2's, and before looking at load 0.5.
* H1: mean per-seed difference DR(S2) - DR(S0-QoS) on the stress cases is at least 10 percentage
  points and its 95% bootstrap interval lies above zero.
* H1b: on the same cases, the mean difference DR_P0(S2) - DR_P0(S0-QoS) is not below -1 point.
* H2: on the uncongested cases, the mean differences of DR and of DR_P0 are each within 1 point.
* H3: S2 has no overloaded arc in any row (every variant, case and load); S0 and S0-QoS have some in
  the stress cases.
* H4: the median S2 `compute_ms` at demo size is under 1000 ms, measured on its own (`summary.json`),
  because the `compute_ms` column is taken with several processes sharing the machine.
* H5: the P0 greedy gap is zero in at least 95% of the default S2 rows; the others are listed.

S2 against S0 on DR_P0 is context, not a hypothesis (S0 has no priority).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

from cli.stats import Summary, paired_differences, summarize

STRESS_CASES = ("uplink", "multi")
STRESS_LOAD = 1.0
UNCONGESTED_CASES = ("healthy", "recovered")
UNCONGESTED_LOAD = 0.5
H1_POINTS = 10.0
H1B_FLOOR = -1.0
H2_TOLERANCE = 1.0
H4_LIMIT_MS = 1000.0
H5_SHARE = 0.95
EPS = 1e-9  # a difference of exactly 10 points must not fail on float rounding

Row = Mapping[str, Any]


@dataclass(frozen=True)
class Verdict:
    id: str
    statement: str
    passed: bool
    measured: str
    detail: dict

    def line(self) -> str:
        return f"{self.id}: {'PASSED' if self.passed else 'FAILED'}  {self.measured}"


def per_seed(rows: Sequence[Row], policy: str, metric: str, cases: Sequence[str], load: float,
             variant: str = "default") -> dict[int, float]:
    """The metric of one policy, per seed, averaged over `cases` at one load factor."""
    chosen = [r for r in rows if r["policy"] == policy and r["case"] in cases and r["load_factor"] == load
              and r["variant"] == variant]
    by_seed: dict[int, list[float]] = {}
    for r in chosen:
        by_seed.setdefault(int(r["seed"]), []).append(float(r[metric]))
    if not by_seed:
        raise ValueError(f"no rows for {policy} {metric} {list(cases)} at load {load}")
    if any(len(v) != len(cases) for v in by_seed.values()):
        raise ValueError(f"{policy}: some seeds lack one of the cases {list(cases)} at load {load}")
    return {seed: math.fsum(v) / len(v) for seed, v in by_seed.items()}


def paired_points(rows: Sequence[Row], metric: str, cases: Sequence[str], load: float,
                  a: str = "S2", b: str = "S0-QoS") -> list[float]:
    """a minus b per seed, in percentage points."""
    return [100 * d for d in paired_differences(per_seed(rows, a, metric, cases, load),
                                                per_seed(rows, b, metric, cases, load))]


def _fmt(s: Summary, unit: str = "pp") -> str:
    return f"mean {s.mean:+.2f} {unit}, median {s.median:+.2f}, 95% CI [{s.low:+.2f}, {s.high:+.2f}], n={s.n}"


def h1(rows: Sequence[Row]) -> Verdict:
    s = summarize(paired_points(rows, "dr", STRESS_CASES, STRESS_LOAD))
    return Verdict("H1", "On stress cases S2 beats S0-QoS on DR by at least 10 points, with the 95% interval above 0",
                   s.mean >= H1_POINTS - EPS and s.low > 0, _fmt(s), asdict(s))


def h1b(rows: Sequence[Row]) -> Verdict:
    s = summarize(paired_points(rows, "dr_p0", STRESS_CASES, STRESS_LOAD))
    return Verdict("H1b", "On stress cases S2 DR_P0 is not below S0-QoS DR_P0 by more than 1 point",
                   s.mean >= H1B_FLOOR - EPS, _fmt(s), asdict(s))


def h2(rows: Sequence[Row]) -> Verdict:
    dr = summarize(paired_points(rows, "dr", UNCONGESTED_CASES, UNCONGESTED_LOAD))
    p0 = summarize(paired_points(rows, "dr_p0", UNCONGESTED_CASES, UNCONGESTED_LOAD))
    passed = abs(dr.mean) <= H2_TOLERANCE + EPS and abs(p0.mean) <= H2_TOLERANCE + EPS
    return Verdict("H2", "On uncongested cases S2 DR and DR_P0 are within 1 point of S0-QoS", passed,
                   f"DR {_fmt(dr)}; DR_P0 {_fmt(p0)}", {"dr": asdict(dr), "dr_p0": asdict(p0)})


def h3(rows: Sequence[Row]) -> Verdict:
    s2 = sum(1 for r in rows if r["policy"] == "S2" and int(r["overloaded_arcs"]) > 0)
    in_stress = [r for r in rows if r["case"] in STRESS_CASES and r["load_factor"] == STRESS_LOAD]
    stress = {p: sum(1 for r in in_stress if r["policy"] == p and int(r["overloaded_arcs"]) > 0)
              for p in ("S0", "S0-QoS")}
    s2_rows = sum(1 for r in rows if r["policy"] == "S2")
    return Verdict("H3", "S2 has no overloaded arc; S0 and S0-QoS have some in the stress cases",
                   s2 == 0 and all(v > 0 for v in stress.values()),
                   f"S2 rows with an overloaded arc: {s2} of {s2_rows}; stress rows with one: "
                   f"S0 {stress['S0']}, S0-QoS {stress['S0-QoS']}",
                   {"s2_violations": s2, "s2_rows": s2_rows, "baseline_stress_rows": stress})


def h4(summary: Mapping[str, Any]) -> Verdict:
    timing = summary.get("h4_compute_ms")
    if not isinstance(timing, Mapping):
        return Verdict("H4", "The S2 recompute at demo size is under 1 second", False,
                       "not measured: summary.json has no h4_compute_ms", {})
    median = float(timing["median"])
    return Verdict("H4", "The S2 recompute at demo size is under 1 second", median < H4_LIMIT_MS,
                   f"median {median:.0f} ms over {timing['repeats']} runs "
                   f"({timing['case']}, load {timing['load_factor']})",
                   dict(timing))


def h5(rows: Sequence[Row]) -> Verdict:
    s2 = [r for r in rows if r["policy"] == "S2" and r["variant"] == "default"]
    if not s2:
        raise ValueError("no default S2 rows")
    nonzero = [r for r in s2 if abs(float(r["p0_greedy_gap"])) > EPS]
    share = 1 - len(nonzero) / len(s2)
    keys = ("seed", "case", "load_factor", "p0_greedy_gap")
    listed = [{k: r[k] for k in keys} for r in nonzero]
    return Verdict("H5", "The P0 greedy gap is zero in at least 95% of the default S2 runs", share >= H5_SHARE - EPS,
                   f"zero in {share:.1%} of {len(s2)} runs; {len(nonzero)} with a gap",
                   {"share_zero": share, "runs": len(s2), "non_zero": listed})


def evaluate(rows: Sequence[Row], summary: Mapping[str, Any]) -> list[Verdict]:
    return [h1(rows), h1b(rows), h2(rows), h3(rows), h4(summary), h5(rows)]
