## Context

PLAN.md section 5 gives `on_event` and argues for a full priority-ordered recompute on every event. Section 4 lists the trade-off: churn is accepted and measured in exchange for having no state carried between events. Section 9 lists eight scenario fixtures, invariant I8 (determinism) and the equality of simultaneous and sequential failures.

## Goals / Non-Goals

**Goals:**
- One `Simulation` class used unchanged by the API, the CLI and the tests.
- Final state depends only on the set of down links, never on event history.
- A scenario is data: a JSON file fully determines a run.

**Non-Goals:**
- Incremental or sticky rerouting, time-varying traffic, tick simulation, cascading failures, SRLG.
- Session storage (the API owns that) and persistence.

## Decisions

**Full recompute on every event, fail or recover.** The simulation calls `policy.route(topo, flows, current_alloc, cfg)` and replaces the allocation.
*Rejected:* rerouting only the affected flows, because unaffected P2 flows could hold capacity that an affected P0 flow needs (section 5).

**An event is atomic.** All links in one event change state before any routing. A `node` on a fail event expands to all incident links, and on a recover event recovers them.
*Rejected:* one event per link, because a simultaneous failure would then produce intermediate snapshots that never existed.

**Events are idempotent.** Failing a down link or recovering an up link changes nothing in the topology. The event still produces a snapshot with the next step number, so the UI and the event list stay aligned.
*Rejected:* raising an error, because section 13 lists both as no-ops and a double click must not break the demo.

**Affected flows are computed after the topology change and before routing**, from the current allocation: any flow with a path through an arc that is now down. A recovery event affects no flow.
*Rejected:* diffing paths after routing, because that measures churn, which section 8 defines separately.

**The simulation keeps the step-0 topology and flows for `reset`.** `reset` restores all link states from the scenario, clears the allocation, routes once and returns the step-0 snapshot.
*Rejected:* building a new simulation on reset, because a generator scenario would be resolved again and the API session would need a new run id.

**Wall-clock is measured here.** The simulation times the `route` call and passes `compute_ms` to the metrics function. It is the only non-deterministic field in a snapshot.
*Rejected:* timing inside the policy, because `route` must be pure and read no clock (section 7).

**Invariant checking is a constructor flag.** On in tests, optional in the demo. On failure it raises with the invariant id.
*Rejected:* always on, because section 5 makes it optional in the demo, where its cost adds to every click.

**Unknown ids are errors.** An event naming a link or node not in the topology raises before any state changes. A scenario whose flows reference unknown nodes fails at load.
*Rejected:* ignoring unknown ids, because a mistyped link in a scenario file would then pass as a harmless no-op.

**Scenario fixtures carry their assertions as data.** Each fixture JSON has the `Scenario` plus an `expect` block (exact deliveries for the diamond, "final snapshot equals" for scenario 3, "equals step 0" for scenario 8). One parametrised test runs every fixture. Expected numbers are hand-worked before the code runs.
*Rejected:* assertions in one Python test per fixture, because the scenario and its expectation would live apart and a person reviewing the fixture could not see what it claims.

**Determinism.** The simulation uses no randomness; the seed in a scenario is consumed only by the generators. Links named in an event are applied in sorted id order, affected flows are listed sorted by id, `link_state` is emitted in link-id order, and each policy in a comparison gets its own deep copy. Serialization for the I8 comparison uses sorted keys and masks `metrics.compute_ms`.
*Rejected:* comparing snapshots as Python objects only, because byte identity of the serialized form is what I8 states and what a diff between two runs needs.

## Risks / Trade-offs

- [Recovery does not restore the step-0 allocation exactly] → This would be a determinism bug; fixture 8 asserts equality.
- [Hidden iteration-order dependence] → The I8 byte-identity test, and a run of the same scenario in two fresh processes.
- [Full recompute is slow on large networks] → Measured at demo size (hypothesis H4); optimizations are on the roadmap.
- [Scenario fixtures are added after the freeze] → All four members agree to each, and the fixture lands before the code that must pass it.
- [Churn of lower-class flows surprises a viewer] → Churn is a reported metric and is explained in the README.
