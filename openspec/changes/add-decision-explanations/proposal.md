## Why

A dropped flow with no stated reason is a mystery drop. PLAN.md section 10 makes the per-flow explanation one of the visible differentiators: every decision is recorded, every shortfall has a cause, and a max-flow check separates a physical limit from a heuristic shortfall.

## What Changes

- Add a **decision record** per flow per event for every policy, with the reference path and why it was not used.
- Add the per-push **attempt** log for S1 and S2 (path, cost, latency, bottleneck, amount pushed).
- Add the **residual cut** for flows unserved through insufficient capacity: the saturated or failed arcs separating source from destination, with the load held on them by class.
- Add the per-flow **max-flow bound** and **greedy gap** for unserved S1/S2 flows.
- Add the **one-line explanation**, generated from the record by a fixed template and never by free text.
- Add the lazy mode for the bound (cut line for assumption A3): compute it on request by replaying the allocation up to that flow.

## Non-goals

- Enumerating alternative paths (no Yen; PLAN.md section 3).
- Free-text or generated-language explanations.
- Changing any allocation: this module only describes one.
- Displaying records (`add-frontend-ui`) or serving them (`add-rest-api`).

## Capabilities

### New Capabilities
- `decision-log`: decision records, reference-path status, attempts, residual cut, max-flow bound, greedy gap and the templated explanation.

### Modified Capabilities

None.

## Impact

- **Owner:** A.
- **Folders:** `core/explain/` only (including its tests in `core/explain/tests/`).
- **PLAN.md sections implemented:** 5 (unserved remainder, cut, `maxflow_bound`, `greedy_gap`, known weakness), 7 (`DecisionRecord`, `Attempt`, `CutArc`), 10 (decision log, cut rule, explanation template), 12 (H4 to H12 for A; the A3 cut line).
- **Frozen contract:** not touched. The record types and the section 10 example fixture are created by `add-core-model-contract`; this change reads them. If the builder cannot produce that fixture exactly, the mismatch is raised with all four members and not fixed by editing the fixture.
- **Depends on:** `add-core-model-contract` (`DecisionRecord`, `Ledger`) and the pathfinder from `add-routing-policies`.
- **Depended on by:** the policies (which call the builder), `add-metrics-invariants` (P0 greedy gap, I11), `add-rest-api` (decision endpoint), `add-frontend-ui` (decision panel).
- **Window:** records with bound H4 to H8; cut explanations H8 to H12.
