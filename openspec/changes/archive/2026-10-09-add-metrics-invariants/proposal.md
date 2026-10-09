## Why

Every claim in the demo is a number, and the rule in PLAN.md section 15 is that every spoken number comes from the final benchmark run. The metrics must therefore be computed from the simulated state alone so they cannot disagree with it, and an independent checker must confirm that each snapshot obeys the model's constraints.

## What Changes

- Add the metrics of section 8 as pure functions of `(topology, flows, allocation)`: delivery ratio overall, by class and reachable-only; unserved by cause; overload count and excess; max and mean utilization and arcs above 90%; per-link display utilization; latency stretch; recovery ratio; churn; P0 greedy gap; weighted delivery (secondary).
- Add `check_invariants`, covering invariants I1 to I11 of section 9, run on every snapshot in tests.
- Add hand-computed metric cases as tests.

## Non-goals

- Aggregation over seeds, confidence intervals and hypothesis evaluation (`add-cli-benchmark`).
- The hypothesis property tests, which D writes on top of the checker (`add-cli-benchmark`).
- The LP optimality gap.
- Any metric computed in the browser.

## Capabilities

### New Capabilities
- `metrics`: all reported measures and the per-link display rule.
- `invariant-checking`: the I1 to I11 checker over snapshots.

### Modified Capabilities

None.

## Impact

- **Owner:** B (moved from D; PLAN.md section 11, "Why metrics moved to B").
- **Folders:** `core/metrics/` only (including its tests in `core/metrics/tests/`).
- **PLAN.md sections implemented:** 4 (load, residual, utilization definitions), 7 (`Metrics`, link display rule), 8 (all formulas), 9 (invariants I1 to I11), 12 (B's column).
- **Frozen contract:** not touched. This change reads the `Metrics` model and the diamond fixtures and edits neither.
- **Depends on:** `add-core-model-contract`. Invariants I10 and I11 need the allocator and the decision records to exercise them.
- **Depended on by:** `add-simulation-engine` (snapshot assembly, optional checking), `add-rest-api`, `add-cli-benchmark` (hypothesis evaluation), `add-frontend-ui` (KPI strip, link colour).
- **Window:** basic metrics H1.5 to H4; full metrics and checker H4 to H8; I11 H8 to H12.
