## Context

PLAN.md section 8 defines the formulas and section 9 the invariants. Section 11 moved metrics and the checker from D to B because they are pure functions of B's own types and D was on the critical path of every milestone. The checker is deliberately separate from the allocator so that an allocator bug cannot hide itself.

## Goals / Non-Goals

**Goals:**
- Metrics are recomputable from a snapshot (invariant I9).
- The checker shares no code with the policies.
- Hand-computed cases exist for every formula.

**Non-Goals:**
- Benchmark aggregation over seeds, confidence intervals and hypothesis evaluation (`add-cli-benchmark`).
- The LP optimality gap.

## Decisions

**One entry point: `compute_metrics(topology, flows, allocation, *, previous, affected, healthy_latency, decisions, compute_ms)`.** The first three arguments define the state. `previous` and `affected` serve recovery ratio and churn. `healthy_latency` is the per-flow shortest latency on the healthy topology, computed once per scenario. `decisions` supplies `greedy_gap`. `compute_ms` is passed through.
*Rejected:* one public function per metric, because callers could then pass different state to different metrics and the snapshot would be inconsistent.

**Utilization uses raw capacity.** `u = load / capacity`, per section 4, so with `util_cap` 0.9 a full arc shows 0.9. Max, mean and above-90% are taken over available arcs. `link_util[link]` is the larger of its two arc utilizations; a down link is reported as 0 and the UI draws it from `link_state`.
*Rejected:* dividing by the capped capacity, because section 4 defines `u_a = L_a / c_a` and the display would otherwise show "100%" on a link held to 90%.

**Overload is measured against raw capacity for every policy.** The count of arcs with `load > capacity`, and the sum of the overshoot. S1 and S2 are zero by construction.
*Rejected:* measuring against the capped capacity, because the baselines have no cap and the policies would be compared on different scales.

**Latency stretch is 1.0 when nothing is delivered.** `sum(d_f * lat_f) / sum(d_f * lat0_f)`, where `lat_f` is the rate-weighted latency of the flow's paths; flows with no delivery contribute nothing.
*Rejected:* reporting it as unset, because the `Metrics` model types `latency_stretch` as `float`.

**Recovery ratio is unset when undefined**: at step 0, when no flow is affected, or when the affected flows delivered nothing before the event.
*Rejected:* reporting 1.0, because it would read as a full recovery when nothing was recovered.

**Churn compares path sets with their rates.** A flow has churned when its set of `(arcs, rate)` pairs differs from the previous allocation. `churn_rate` is the integer sum of path rates on new or changed paths. Step 0 has no churn.
*Rejected:* comparing arcs only, because traffic shifted between two unchanged paths has still moved.

**A ratio with zero demand is 1.0.** This covers `dr` with no flows and a class with no flows.
*Rejected:* 0.0 or NaN, because 0.0 reads as total failure and NaN is not valid JSON.

**Float comparisons use a tolerance of 1e-9**, in the formula tests and in the checker.
*Rejected:* exact equality on `Fraction` values, because the contract stores deliveries as floats.

**The checker returns a list of violations, each with an invariant id.** A thin wrapper raises on a non-empty list. Per-snapshot checks (I1, I2, I3, I4, I6, I7, I9, I11) take a snapshot with its topology, flows and policy name. I5 is a ledger test. I8 and I10 compare two runs and are helper functions used by tests.
*Rejected:* raising at the first violation, because a person debugging a failed seed wants every broken invariant at once.

**The checker rebuilds everything itself.** Arc load, components and path validity come from the model helpers and a plain networkx connectivity query. I7 verifies `DISCONNECTED` and `INSUFFICIENT_CAPACITY` this way.
*Rejected:* reusing the routing pathfinder or the allocator's ledger, because a bug shared with the code under test would pass unnoticed.

**Determinism.** No randomness is used. Every sum iterates flows in id order and arcs in arc-id order, so float sums are bit-identical between runs. Dict-valued metrics (`dr_by_class`, `unserved_by_cause`, `link_util`) are built in sorted key order, and violations are returned sorted by invariant id, then flow or arc id.
*Rejected:* summing in dict order, because float addition is not associative and a different order could change the last bits and break I8.

## Risks / Trade-offs

- [Metrics and checker share a bug with the policy] → No shared code path; expected values are hand-worked.
- [Float noise fails I3 or I9] → Tolerance 1e-9 everywhere.
- [Per-link max hides a quiet reverse direction] → Accepted; the UI needs one colour per edge and the per-arc values stay in the allocation.
- [Checker cost in the demo] → Checking is optional outside tests.
