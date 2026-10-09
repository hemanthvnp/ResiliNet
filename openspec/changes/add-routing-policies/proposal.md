## Why

Routing is the submission. PLAN.md section 1 commits to two baselines and one residual-capacity engine in two configurations, compared on identical scenarios, with S0-QoS as the fair baseline every headline number is quoted against.

## What Changes

- Add `pathfinder.py`, the single wrapper around networkx: deterministic Dijkstra with tie-break `(cost, hops, node ids)`, connected components, reachability on a residual graph, and max-flow value.
- Add **S0**: latency shortest path per flow, no capacity check, proportional loss on overloaded arcs.
- Add **S0-QoS**: the same routes as S0, with each arc serving classes in strict priority order.
- Add the **allocator**: flows placed in order on the residual-capacity graph by repeated shortest-path pushes, split over at most `max_paths` paths, with an optional integer congestion penalty on arc cost.
- Add **S1** (arrival order, one path, latency-only cost) and **S2** (class priority order, splitting, optional congestion cost) as two configurations of that allocator.
- Add a policy registry so the API, CLI and benchmark select policies by name.
- Optional, only if core is stable at H12: upstream-aware baseline delivery behind a flag, and an LP reference labelled "fractional upper bound".

## Non-goals

- k-shortest-path enumeration, rip-up and reroute, sticky or incremental rerouting (PLAN.md sections 3 and 4).
- Global optimality of delivered traffic.
- Building decision records and explanation text (`add-decision-explanations`).
- Event handling and metrics (`add-simulation-engine`, `add-metrics-invariants`).

## Capabilities

### New Capabilities
- `pathfinding`: deterministic shortest path, components, residual reachability and max-flow value behind one module.
- `baseline-routing`: S0 and S0-QoS routes and their single-pass delivery models.
- `capacity-aware-allocation`: the S1/S2 allocator, ordering policies, flow splitting, congestion cost, cause assignment and its guarantees.

### Modified Capabilities

None.

## Impact

- **Owner:** A.
- **Folders:** `core/routing/` only (including its tests in `core/routing/tests/`).
- **PLAN.md sections implemented:** 1 (four policies), 3 (approaches 1, 3, 4, 5, 6; 7 as optional), 4 (constraints, edge-case semantics, guarantees, diamond example), 5 (cost function, S0, S0-QoS, allocator pseudocode, design knobs), 7 (`RoutingPolicy`, tie-break rule), 12 (A's column and the H8 cut lines), 13 (edge cases).
- **Frozen contract:** not touched. This change reads `core/model/types.py` and the diamond fixtures and edits neither.
- **Depends on:** `add-core-model-contract` (types, arcs, `Ledger`) and the record builder from `add-decision-explanations`.
- **Depended on by:** `add-simulation-engine`, `add-rest-api`, `add-cli-benchmark`.
- **Window:** pathfinder and baselines H1.5 to H4; allocator H4 to H8; ablation tuning H8 to H16.
