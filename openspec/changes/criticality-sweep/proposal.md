## Why

The problem statement lists resilience scoring as a standout item, including flagging "the single link whose loss would hurt most". Cycle 1 only tests failures the user picks, so it cannot say which link is the campus's weakest point, or how each policy fares when that link goes.

## What Changes

- Add a single-link sensitivity sweep that fails each link of a scenario's healthy topology, one at a time.
  - It records post-failure `DR_P0` and `DR`, the drop of each from the policy's healthy value, overloaded arcs and unreachable demand.
  - It groups the links into structural (bridges) and operational, ranks each group per policy with shared ties, and writes a CSV plus a printed summary.
- Add the command `python -m ext sweep --scenario <file|id> [--policies ...] [--out file.csv]`.

## Capabilities

### New Capabilities
- `criticality-sweep`: single-link sensitivity sweep with structural and operational link rankings per policy.

### Modified Capabilities
None.

## Owner and scope

- **Owner:** D (integration and QA), who owns `ext/` and `examples/` for cycle 2 (PLAN-CYCLE2.md §7, §8).
- **Folders:** `ext/` (new). No cycle-1 folder is edited.
- **Plan sections:** PLAN-CYCLE2.md §3.2, §7. PLAN.md §8 (metrics), §9 (identical conditions across policies), §14 (roadmap: vulnerability analyzer).
- **Frozen contract:** not touched. It reads `Snapshot` and `Metrics` as they are.

## Non-goals

- Multi-link (k-failure) sweeps or a Monte-Carlo robustness curve. These are deferred to cycle 3 (PLAN-CYCLE2.md §5).
- No UI panel or chart. The frontend is frozen.
- Not part of the H16 benchmark or hypotheses H1 to H5.

## Impact

- **New code:** `ext/sweep.py`, plus a `sweep` subcommand in `ext/__main__.py` and `ext/tests/test_sweep.py`.
- **Depends on cycle 1:** `Simulation` (`apply`, `reset`), `Metrics`, the policy registry and the scenario loader.
- **Runtime:** one recompute per link per policy, about 1 to 2 minutes per policy on the campus template.
