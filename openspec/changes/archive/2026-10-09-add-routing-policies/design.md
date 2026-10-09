## Context

PLAN.md section 5 gives the pseudocode for all four policies and section 4 gives the constraints, the guarantees and the diamond worked example with exact numbers. The allocator is a greedy heuristic: it guarantees the hard constraints and class isolation, and does not guarantee maximum delivered traffic.

## Goals / Non-Goals

**Goals:**
- S0, S0-QoS, S1, S2 behind one `RoutingPolicy` interface, pure and deterministic.
- The diamond table reproduced exactly for S0, S0-QoS and S2, in both rows.
- S1 and S2 always satisfy hard constraints 1 to 5.
- Knobs (`order`, `max_paths`, `congestion_lambda`, `util_cap`) are configuration, chosen by ablation.

**Non-Goals:**
- k-shortest-path enumeration, rip-up and reroute, sticky rerouting, incremental recompute.
- Global optimality. The LP reference is optional and offline.
- Building the explanation text (`add-decision-explanations`).

## Decisions

**One allocator function, two configurations.** S1 is `order=arrival, max_paths=1, congestion_lambda=0`; S2 is `order=class_size_desc, max_paths=3` with `congestion_lambda` 0, as the ablation chose (below).
*Rejected:* separate S1 and S2 implementations, because two code paths can diverge and the ablation would no longer isolate one variable.

**`arrival` order ignores class; the two `class_size_*` orders sort by class first.** Arrival order is the order of the input flow list.
*Rejected:* arrival order within class, because S1 would then have priority and the ablation could not show what priority is worth.

**All networkx calls live in `pathfinder.py`, and Dijkstra is our own.** The pathfinder runs a heap-based Dijkstra with integer weights and the heap key `(cost, hops, node-id tuple)`. Components and max-flow use networkx directly.
*Rejected:* `networkx.shortest_path` with a weight callable, because its tie-breaking depends on insertion order and library version.

**Arc cost is an integer.** `w = latency + lambda * (s(u) - 1)` with the Fortz-Thorup slopes 1, 3, 10, 70 at thresholds 1/3, 2/3, 0.9. Utilization is compared with the thresholds in integer arithmetic (`3 * load < capacity`, and so on).
*Rejected:* float utilization compared with float thresholds, because a rounding difference at a threshold could flip a path between machines.

**Baseline delivery is the single-pass model.** S0 scales each flow by the worst `min(1, c / L)` on its path; S0-QoS computes per-arc, per-class scale factors in priority order. `Allocation.arc_load` holds offered load, so baseline utilization can exceed 1. The model under-delivers for the baselines, which favours S2; the README states this.
*Rejected:* the upstream-aware model as the default, because it must iterate to a fixed point and is on the path to no milestone. It stays optional, behind a flag.

**Baseline causes.** No path gives `DISCONNECTED`; a scale factor below 1 gives `OVERLOAD_LOSS`; otherwise `NONE`.
*Rejected:* reusing `INSUFFICIENT_CAPACITY` for baseline loss, because baselines admit everything and lose it on the link, which the contract names separately.

**Every call is a full recompute from an empty ledger.** `prev` is passed to the record builder for the log only and is never read by the placement loop.
*Rejected:* keeping old paths when still valid (sticky rerouting), because it carries state between events and makes sequential and simultaneous failures diverge (section 4).

**Cause for the allocator.** `DISCONNECTED` is decided up front from components of the available graph. With demand left after the push loop: `PATH_LIMIT` when a path still exists over arcs with residual above zero, otherwise `INSUFFICIENT_CAPACITY`.
*Rejected:* deciding the cause from the max-flow bound, because the bound is optional at route time (A3 cut line) and the cause must not depend on it.

**Degenerate flows are served, not rejected.** `src == dst` is delivered in full with no path. A zero-rate flow is delivered (0 of 0) with cause `NONE`.
*Rejected:* raising on such input, because section 13 lists both as cases to handle and a scenario file should not crash a run.

**The allocator emits records through the explain module.** It collects facts per flow (attempts, reference path, remaining demand, ledger state) and calls the builder in `core/explain/`.
*Rejected:* formatting records inside the allocator, because A must be able to walk through every line of it for the judges.

**The S2 defaults are the measured ones, and the congestion cost stays in the code at 0.** The ablation on 30 campus networks (50 nodes, 200 flows; `python -m core.routing.tests.ablation`) found nothing that beats `class_size_desc`, `max_paths` 3, lambda 0 and `util_cap` 1.0: `max_paths` 1 loses 1 to 7 points of DR, 2 loses at most 0.3 and 4 equals 3; every lambda above 0 lowers DR by 0.2 to 3.3 points and raises latency stretch by 7 to 30%; `util_cap` 0.9 costs 0.3 to 6 points for no delivery gain. The congestion cost therefore fails the criteria fixed beforehand.
*Rejected:* removing it now. `PolicyConfig.congestion_lambda` is part of the frozen contract, D's benchmark toggles it, and at light load (0.5) it does move traffic off nearly-full arcs (25 down to 11 arcs at least 90% full) with no change in delivery. Decided by A on 2026-10-09: keep the code, keep the default at 0, and revisit if the four members agree to a contract change.

**Determinism.** No randomness is used. Baselines process flows sorted by id; the allocator orders flows by its ordering policy with flow id as the last key. Dijkstra expands arcs in sorted arc-id order and breaks ties by `(cost, hops, node ids)`. All costs are integers. `route` reads no clock and no global.
*Rejected:* iterating the input list or a dict as given, because the result would then depend on the order flows appear in a file.

## Risks / Trade-offs

- [Greedy is order-sensitive and can leave a feasible P0 flow unserved] → Reported per flow as `greedy_gap`; hypothesis H5 tracks it; optimality is never claimed.
- [S2 loses to S0-QoS at the H8 headline check] → Treated as a bug or greedy shortfall; A fixes it before any ablation work.
- [S2 fails invariants at H8] → Cut line: `congestion_lambda = 0` and `max_paths = 2`, keeping splitting.
- [Recompute exceeds 1 second (A3)] → Max-flow bounds become lazy (`add-decision-explanations`), then `max_paths = 2`.
- [Congestion cost shows no benefit] → Remove it and report that. A smaller algorithm is preferred. **Outcome:** it showed no benefit on the criteria fixed beforehand (PR 13); it is kept in the code with the default 0, not removed, for the reason under Decisions.
- [Baseline seen as a strawman] → S0-QoS is never cut, and the single-pass bias is disclosed.
