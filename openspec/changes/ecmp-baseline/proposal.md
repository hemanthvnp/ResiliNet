## Why

Equal-cost multipath (ECMP) is the most common way real routers spread load, and both the problem statement and the feasibility research name it as the existing technique to beat. "Why not just ECMP?" is a likely judge question, and cycle 1 compares only against single-path baselines (S0, S0-QoS), so it has no answer backed by numbers.

## What Changes

- Add two ECMP-style baseline policies, `ECMP` and `ECMP-QoS`.
  - At every node, each flow is split equally, in whole Mbps, across its equal-cost latency-shortest next hops.
  - Delivery then uses the cycle-1 S0 and S0-QoS models unchanged.
  - This is an idealised approximation of router ECMP, which hashes flows, and is labelled as such.
- Register both by name, so they work with `run` and `compare` through `python -m ext`.
- Add three hand-worked example scenarios:
  - `square`: equal-cost paths that ECMP can use
  - `shared-prefix`: shows that the split is per next hop, not per path
  - `eight-paths`: a case where ECMP-QoS out-delivers S2 at S2's default path limit

## Capabilities

### New Capabilities
- `ecmp-routing`: equal-cost multipath baselines with proportional and strict-priority delivery.

### Modified Capabilities
None. The cycle-1 `baseline-routing` and `capacity-aware-allocation` requirements are unchanged.

## Owner and scope

- **Owner:** D (integration and QA), who owns `ext/` and `examples/` for cycle 2 (PLAN-CYCLE2.md §7, §8).
- **Folders:** `ext/` (new) and `examples/` (new). No cycle-1 folder is edited.
- **Plan sections:** PLAN-CYCLE2.md §3.1, §7. PLAN.md §3 (approach table), §5 (baseline delivery models), §14 (policies register by name).
- **Frozen contract:** not touched. Path rates stay integers, so `PathAlloc.rate: int` holds.

## Non-goals

- No UI or API change. The baseline selector stays S0-QoS / S0.
- Not part of the H16 cycle-1 benchmark, and not part of hypotheses H1 to H5.
- Not a model of flow hashing or of unequal-cost multipath (UCMP).
- No claim that S2 beats ECMP on delivery. Delivery and overload are reported separately.

## Impact

- **New code:** `ext/ecmp.py`, `ext/__main__.py`, `ext/tests/`.
- **New data:** `examples/square.json`, `examples/shared-prefix.json` and `examples/eight-paths.json`.
- **Depends on cycle 1:** the `RoutingPolicy` interface, the policy registry, the S0/S0-QoS delivery formulas and `check_invariants`. The fallbacks are in PLAN-CYCLE2.md §7.
- **No new dependencies.** It uses networkx, which is already in the stack.
