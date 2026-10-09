## Why

The policies route a static network. The product is what happens when links fail and recover: PLAN.md section 5 defines an event loop that applies an event, recomputes routes in full, and returns a snapshot that the API, CLI and UI all consume.

## What Changes

- Add `Simulation`: holds topology state and the current allocation for one scenario, one policy and one config, with `apply(event)` and `reset()`.
- Add event handling: `fail` and `recover` of one or more links as a single atomic event, node failure as sugar for failing all incident links, idempotent repeats.
- Add affected-flow detection, computed before rerouting.
- Add snapshot assembly: step, link state, allocation, metrics, affected flows, decisions.
- Add the scenario loader: JSON file or inline `Scenario` to a ready simulation, resolving topology and traffic specs, and a runner that plays a scenario's event list.
- Add the eight scenario fixtures of section 9 as JSON inputs with assertions.
- Add the determinism check: same scenario, config and seed give a byte-identical snapshot sequence once `metrics.compute_ms` is masked.

## Non-goals

- Incremental or sticky rerouting, time-varying traffic, tick simulation, cascading failures, shared-risk link groups (PLAN.md sections 4 and 14).
- Session storage, which the API owns, and persistence.
- Metric formulas and the invariant checker (`add-metrics-invariants`); this change calls them.

## Capabilities

### New Capabilities
- `simulation-events`: the simulation state machine, fail/recover/node events, full recompute, affected flows and snapshots.
- `scenarios`: scenario loading and running, the eight fixtures, and reproducibility from a seed.

### Modified Capabilities

None.

## Impact

- **Owner:** B.
- **Folders:** `core/sim/` (including its tests in `core/sim/tests/`) and `fixtures/scenarios/` for the eight scenario files.
- **PLAN.md sections implemented:** 2 (node failure as sugar), 5 (event handling, full recompute), 6 (data flow), 7 (`Simulation`, `Scenario`, `Snapshot`, reproducibility rules), 9 (scenario fixtures 1 to 8, invariant I8, identical conditions), 12 (B's column), 13 (edge cases).
- **Frozen contract:** touched. The eight scenario files are added under `fixtures/` after the H1.5 freeze. Each addition needs all four members to agree, and the fixture is written, with hand-worked expectations, before the code that must pass it. `core/model/types.py` is not touched.
- **Depends on:** `add-core-model-contract`, `add-network-generators` (spec resolution), `add-routing-policies` (policy registry), `add-metrics-invariants` (metrics and the checker).
- **Depended on by:** `add-rest-api` (one `Simulation` per session), `add-cli-benchmark`.
- **Window:** minimal `apply` H1.5 to H4; full semantics, determinism and fixtures 1 to 7 H4 to H8; fixture 8 H8 to H12.
