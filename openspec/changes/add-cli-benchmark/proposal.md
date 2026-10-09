## Why

Correctness has to be checkable without the UI, and the headline claim (S2 against S0-QoS) has to rest on more than one hand-tuned network. PLAN.md section 9 defines an experimental method, five hypotheses stated before running, and a rule that only numbers from the final run on frozen code are spoken in the demo.

## What Changes

- Add a CLI over the core library: run a scenario under one policy, compare policies on one scenario, and run the benchmark, writing JSON and CSV.
- Add the benchmark: 30 seeds of the campus generator with a random failure set each, all four policies on identical conditions, a load-factor sweep, and one-knob-at-a-time ablations of S2.
- Add timing of the first seed and automatic sizing of the matrix to a 30-minute budget.
- Add results tables with mean, median and 95% bootstrap confidence intervals, and the evaluation of hypotheses H1 to H5 against S0-QoS.
- Add hypothesis property tests asserting invariants over random scenarios.
- Add the README (setup, model, algorithm, architecture, reproduction, results, limitations) and the demo deliverables (script, fallback run JSON, recorded video).

## Non-goals

- The scaling study across network sizes, extra generators, the Monte-Carlo robustness curve (PLAN.md sections 9 and 14).
- Charts; the frontend draws them from the CSV.
- Invariant logic; the property tests call B's checker.
- The LP reference (optional, in `add-routing-policies`).

## Capabilities

### New Capabilities
- `cli`: command-line run, compare and benchmark commands with file output.
- `benchmark`: the seeded experiment matrix, statistics, hypothesis evaluation and property tests.

### Modified Capabilities

None.

## Impact

- **Owner:** D. If D is behind at H12, B takes over the benchmark run or the results tables (PLAN.md section 11); that handover is agreed in chat, and B then works in `cli/` at D's request.
- **Folders:** `cli/` and `tests/` (`tests/cli/`, `tests/property/`). The root `README.md` and the `results/` output folder belong to no member's folder; PLAN.md sections 11 and 12 assign them to D.
- **PLAN.md sections implemented:** 6 (CLI over the core), 8 (headline set), 9 (experimental method, hypotheses H1 to H5, property tests), 11 (D's row), 12 (D's column, benchmark reruns, cut lines), 15 (definition of done, demo script).
- **Frozen contract:** not touched. The benchmark reads fixtures and writes only under `results/`.
- **Depends on:** every core change: model, generators, routing, explanations, simulation, metrics.
- **Depended on by:** `add-frontend-ui` (benchmark chart reads the CSV).
- **Window:** property tests and CLI H4 to H8; CSV and matrix sizing H8 to H12; full run and hypotheses H12 to H16; README H16 to H20; fallback recording H20 to H22.
