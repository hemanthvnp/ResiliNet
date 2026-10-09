## Context

See proposal.md for the motivation. The cycle-1 baselines (PLAN.md §5, change `add-routing-policies`) route each flow on one latency-shortest path. S0 then applies proportional per-arc loss, and S0-QoS strict per-class priority per arc. The frozen contract stores path rates as integers (`PathAlloc.rate: int`) and deliveries as floats. Cycle-2 code must not edit any member's folder or the contract (PLAN-CYCLE2.md §2, §7).

## Goals / Non-Goals

**Goals:**
- An ECMP-style baseline that a networking judge accepts as an honest, clearly labelled approximation of ECMP on aggregate flows.
- Exact reuse of the cycle-1 delivery formulas, so ECMP-QoS differs from S0-QoS only in its routes.

**Non-Goals:**
- Flow hashing, unequal-cost multipath, tuning link weights.
- Claiming the model reproduces any real router's ECMP.
- Showing ECMP in the UI or the H16 benchmark.

## Decisions

**Split equally per next hop, not per complete path.**
- Each node divides the traffic it receives equally among its equal-cost next hops, which is how ECMP is configured on routers.
- *Rejected: equal split per complete path.* It is a different policy whenever paths share a first hop. Example (cross-model review C1.1): 120 Mbps over S–A–X–D, S–A–Y–D and S–B–D gives S–A 80 and S–B 40 per path, but 60 and 60 per next hop.

**Integer split, with branches carried down a depth-first walk.**
1. Compute `dist` to the destination with Dijkstra on the reversed available graph.
2. Walk from the source, carrying an integer amount. At each node, divide the amount over the next hops in (node id, link id) order: `amount // n` each, with the remainder given 1 Mbps at a time from the first next hop. Skip any branch that receives 0.
3. Every leaf reached at the destination is a path, and its rate is the amount that arrived along it.

Properties:
- Path rates are integers and sum to the flow's rate.
- A flow has at most `rate` paths, because each path carries at least 1 Mbps. So the walk is bounded without a separate path cap.
- All latencies are integers, so the equal-cost test is exact.
- *Rejected: fractional split rates.* `PathAlloc.rate` is an `int` in the frozen contract.
- *Rejected: splitting a fractional flow and then decomposing it into paths.* The decomposition is not unique, and the rates would not be integers.

**Next-hop width fixed at 8 per node.**
- This is an implementation choice, not a hardware claim. The README states that real routers make this width configurable.
- *Rejected: making it configurable.* `PolicyConfig` is frozen.
- The route-count effect is separated from the routing-policy effect by always also reporting S2 with `--max-paths 8` (an existing cycle-1 flag).
- The eight-route regression case (spec scenario "Eight parallel routes") shows why: at the default `max_paths` 3, S2 delivers 30 against ECMP-QoS's 80. At 8 it delivers 80 with no overload.

**Parallel links are ordered by link id after the node id.**
- *Rejected: ordering by node id only.* Two parallel links to the same neighbour would tie, and the order would depend on the data structure.

**Delivery reuses the cycle-1 formulas, applied per path.**
- A's formulas in `core/routing/baselines.py` are closures inside the single-path route functions, so they cannot be called on a multi-path allocation.
- `ext/ecmp.py` repeats the two formulas, using `Fraction` as A does so the results are exact. A test checks them against `route_s0` and `route_s0_qos` on the diamond.
- Decision records are built with `core.explain.records.build_record`, as the baselines do.
- *Rejected: a new delivery model.* ECMP and S0 would then differ in two ways at once.

**Registration through `ext`, not `core/routing/`.**
- `ext.register()` adds `ECMP` and `ECMP-QoS` to the `POLICIES` dict in `core/routing/registry.py` with `setdefault`. No line of A's code changes.
- Importing `ext` registers nothing. Registering at import time would leak the policies into every other test in the same pytest process.
- `python -m ext run|compare` calls `ext.register()`, then passes its arguments to the cycle-1 CLI.
- *Rejected: adding the policies to `core/routing/`.* That folder is A's, and after H16 any edit there is a feature change to frozen code.

**Determinism.**
- No randomness.
- Flows are processed sorted by id.
- Next hops are ordered by (node id, link id), and the remainder follows that order.
- No clock or global state is read.

## Risks / Trade-offs

- **[Judges say it is not real ECMP]** → It is labelled "ECMP-style, idealised equal split per next hop", and the README states that routers hash flows (PLAN-CYCLE2.md §4).
- **[ECMP-QoS delivers more than S2 on some topology]** → Expected and kept as a regression test. Delivery and overload are always reported separately, and S2 is also reported at `max_paths` 8. S2's decision log explains its own shortfall (`PATH_LIMIT`, greedy gap).
- **[A turns `POLICIES` into an immutable mapping, or D's CLI cannot be called as a function]** → `ext` wraps `get_policy`, or runs the CLI as a subprocess (PLAN-CYCLE2.md §7).
- **[The single-pass delivery bias]** (PLAN.md §5: upstream loss still counts downstream) → It applies to ECMP exactly as to S0 and S0-QoS, and is disclosed the same way.
