## Context

See proposal.md for the motivation. Cycle 1 provides `Simulation(scenario, policy, cfg)` with `apply(event)` and `reset()` (change `add-simulation-engine`), and every event triggers a full recompute. Metrics are computed from the state alone (PLAN.md §8). Cycle-2 code lives in `ext/` and edits no member's folder (PLAN-CYCLE2.md §7).

## Goals / Non-Goals

**Goals:**
- One command answers "which single link failure hurts most, which links disconnect part of the campus, and how does each policy fare?"
- Numbers that are fair across policies and reproducible from the scenario alone.

**Non-Goals:**
- Multiple simultaneous failures, failure probabilities, or repair-order advice. These are cycle 3 (PLAN-CYCLE2.md §5).
- Calling the result "the most critical link in the campus". It is scoped to one topology, traffic matrix and policy configuration (PLAN-CYCLE2.md §4).

## Decisions

**Report absolute post-failure values and drops, side by side.**
- Absolute values answer "how much service is left"; drops answer "how much did the failure cost this policy".
- *Rejected: drop only.* A baseline that already loses traffic while healthy has little left to lose, so it would look resilient.
  - Diamond: S2 drops 0.333 on `DR_P0` while S0-QoS drops 0, yet both end at 0.667.
- *Rejected: absolute only.* It hides how much a policy degrades (cross-model review C3.4).
- Within one policy, ranking by lowest post-failure value and by largest drop give the same order, because the healthy value is the same for every row. So the ranking uses post-failure values, and both columns are printed.

**Structural and operational groups, both always shown.**
- Bridges are found once on the healthy topology with `networkx.bridges`, on the undirected graph of links that are up.
- Their damage is disconnection, which is the same under every policy, so they get their own group with the unreachable demand.
- *Rejected: excluding bridges from the result.* A bridge cutting off a hostel may be the most important link on campus (review C3.2).
- *Rejected: inferring bridges from `DISCONNECTED` causes.* A bridge with no flow across it would be missed.

**Ties share a rank (competition ranking 1, 1, 3).**
- *Rejected: breaking ties by link id.* An arbitrary id would then look like evidence that one tied link is more critical (review C3.1). Link id only orders the rows.

**Reuse `Simulation`, one instance per policy.** For each link: `apply(fail [link])`, read the metrics, then `reset()`.
- *Rejected: calling `policy.route` directly on an edited topology.* That would bypass the event semantics and invariant checks cycle 1 already tests.
- *Rejected: running policies in parallel processes.* The sweep takes minutes, and a process pool adds nondeterministic output order.

**The command is a `sweep` subcommand in `ext/__main__.py`** that uses the cycle-1 scenario loader.
- *Rejected: adding it to `cli/`.* `cli/` is frozen after H16 even for D; the freeze exception covers only `ext/` and `examples/`.

**Determinism.**
- Links are processed in ascending id order.
- Policies are processed in the order given.
- The CSV is sorted by (policy, group, rank, link id).
- No randomness.
- `compute_ms` is not written, so repeated runs are byte-identical.

## Risks / Trade-offs

- **[Every link ties on the demo network, as on the diamond]** → Report it. "No single link is uniquely critical" is a resilience finding in itself, and the structural group still names the disconnecting links.
- **[S2 has a larger drop than S0-QoS]** → Expected wherever S2 delivered more while healthy. Both columns are shown, and the pitch quotes absolute values for service and drops for degradation (PLAN-CYCLE2.md §4).
- **[Runtime on larger generated networks]** → Linear in links × policies. It prints progress and is not on the demo path.
- **[A single failure misses "several failures at once"]** → Stated as a non-goal. Cycle 1's scenario 3 covers one triple failure, and the k-failure experiment is cycle 3.
