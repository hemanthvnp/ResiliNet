## Why

Four members and four AI agents start coding in parallel at hour 0, and every other module reads and writes the same data shapes. PLAN.md section 7 requires those shapes to be frozen at H1.5, and the freeze is valid only if every type is written out and a fixture of each validates.

## What Changes

- Add the repo skeleton: `core/` package with `model/`, `gen/`, `routing/`, `sim/`, `metrics/`, `explain/`, plus `fixtures/`, pinned dependencies and the pytest command.
- Add `core/model/types.py` with every pydantic v2 model in PLAN.md section 7: `Node`, `Link`, `Topology`, `Flow`, `PathAlloc`, `FlowResult`, `Allocation`, `PolicyConfig`, `Event`, `Attempt`, `CutArc`, `DecisionRecord`, `Metrics`, `Scenario` (with `TopologySpec`, `TrafficSpec`), `Snapshot`, and the `RoutingPolicy` protocol.
- Add the directed-arc view of a topology: each physical link gives two arcs with id `"<link>:<u>><v>"`, available only when the link is up.
- Add `Ledger`, the residual-capacity accounting used by the S1/S2 allocator, with per-class load tracking.
- Add JSON fixtures that validate against the models: one snapshot per policy for the diamond, one S0 snapshot with a non-integer `delivered`, and the decision-record example from section 10.
- Add `AGENTS.md` at the repo root (stack, folder ownership, determinism rules, test command, contract-edit rule) and point `CLAUDE.md` to it.

## Non-goals

- Generators, routing, simulation and metric formulas (their own changes).
- The OpenAPI schema and API mocks (`add-rest-api`).
- Campus snapshots: they need the campus template from `add-network-generators`.
- Persistence of any kind.

## Capabilities

### New Capabilities
- `data-model`: the shared typed contract (topology, flows, allocation, events, decision records, metrics, scenario, snapshot), the arc model, and the validating fixtures.
- `capacity-ledger`: residual-capacity accounting per arc with reserve, release, bottleneck and per-class breakdown.

### Modified Capabilities

None.

## Impact

- **Owner:** B. A sits with B to write `DecisionRecord` (PLAN.md section 12, H0 to 1.5); the edit is made by B in B's file.
- **Folders:** `core/model/` (including its tests in `core/model/tests/`) and `fixtures/`. The root files `pyproject.toml` and `AGENTS.md`, and the pointer line in `CLAUDE.md`, belong to no member's folder; PLAN.md sections 11 and 12 assign them to B at H0 to 1.5, so they are part of this change.
- **PLAN.md sections implemented:** 2 (model assumptions), 4 (network and traffic definitions), 7 (data models, `Ledger`, `RoutingPolicy`), 10 (decision-record example), 11 (shared contract, `AGENTS.md`), 12 (H0 to 1.5).
- **Frozen contract:** this change creates it. `core/model/types.py` and `fixtures/` are frozen when its freeze test passes at H1.5. After that, any edit needs all four members to agree, and the fixtures change first.
- **Dependencies:** Python 3.11+, pydantic v2, networkx, pytest, hypothesis, with pinned versions.
- **Depended on by:** every other change.
- **Window:** H0 to H1.5.
