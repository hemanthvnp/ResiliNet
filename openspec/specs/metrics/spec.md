# metrics Specification

## Purpose
TBD - created by archiving change add-metrics-invariants. Update Purpose after archive.

## Requirements

### Requirement: Metrics are a pure function of state
Metrics SHALL be computed from the topology, flows and allocation, plus the previous allocation and affected-flow set for change measures. They SHALL NOT read algorithm internals. Recomputing metrics from a snapshot SHALL give the reported values.

Source: PLAN.md section 8 and 9 (invariant I9).

#### Scenario: Recompute from a snapshot
- **WHEN** metrics are recomputed from a snapshot's allocation
- **THEN** they equal the snapshot's metrics, apart from `compute_ms`

### Requirement: Delivery ratios
`dr` SHALL be total delivered over total demand. `dr_by_class[k]` SHALL be the same ratio over flows of class k. `dr_reach` SHALL be total delivered over the demand of flows whose cause is not `DISCONNECTED`.

Expected values: hand-worked, PLAN.md section 4 (diamond table). The reachable-only case is worked from the formula in section 8; the owner confirms it by hand.

#### Scenario: Diamond under S2, healthy
- **WHEN** metrics are computed for the S2 allocation of the healthy diamond
- **THEN** `dr` is 0.80, `dr_by_class[0]` is 1.00 and `dr_by_class[2]` is 0.50

#### Scenario: Diamond under S0-QoS, healthy
- **WHEN** metrics are computed for the S0-QoS allocation of the healthy diamond
- **THEN** `dr` is 0.40 and `dr_by_class[0]` is 10/15

#### Scenario: Reachable-only delivery
- **WHEN** one of two equal flows is disconnected and the other is fully delivered
- **THEN** `dr` is 0.5 and `dr_reach` is 1.0

### Requirement: Unserved by cause
`unserved_by_cause` SHALL be the sum of `demand − delivered` grouped by cause.

Expected values: worked from the definitions in PLAN.md section 8, not from code; the owner confirms them by hand before the test is written.

#### Scenario: Grouping
- **WHEN** 5 Mbps is unserved for `INSUFFICIENT_CAPACITY` and 10 Mbps for `DISCONNECTED`
- **THEN** `unserved_by_cause` reports 5 and 10 under those causes

### Requirement: Overload measures
`overloaded_arcs` SHALL be the number of arcs with load above capacity and `overload_excess` SHALL be the sum of `load − capacity` over those arcs.

Expected values: hand-worked, PLAN.md section 4 (diamond table).

#### Scenario: Diamond under S0, healthy
- **WHEN** metrics are computed for the S0 allocation of the healthy diamond
- **THEN** `overloaded_arcs` is 2 and `overload_excess` is 30

#### Scenario: Capacity-aware policy
- **WHEN** metrics are computed for any S1 or S2 allocation
- **THEN** `overloaded_arcs` is 0

### Requirement: Utilization measures
Arc utilization SHALL be load over capacity. `max_util`, `mean_util` and `arcs_above_90` SHALL be taken over available arcs. Baseline utilization SHALL be allowed to exceed 1.

Expected values: worked from the definitions in PLAN.md section 4 and 8 (offered load 25 on capacity 10 gives 2.5), not from code; the owner confirms them by hand before the test is written.

#### Scenario: Offered load above capacity
- **WHEN** an arc of capacity 10 carries offered load 25 under S0
- **THEN** `max_util` is 2.5

### Requirement: Per-link display utilization
`link_util` SHALL hold one value per physical link, equal to the larger utilization of its two arcs.

Source: PLAN.md section 7 (link display rule).

#### Scenario: Larger direction wins
- **WHEN** a link's arcs have utilization 0.8 and 0.2
- **THEN** `link_util` for that link is 0.8

### Requirement: Latency stretch
`latency_stretch` SHALL be `sum(delivered × rate-weighted path latency) / sum(delivered × healthy shortest-path latency)` over flows.

Expected values: worked from the definitions in PLAN.md section 8, not from code; the owner confirms them by hand before the test is written.

#### Scenario: Shortest paths only
- **WHEN** every flow is fully delivered on its healthy shortest path
- **THEN** `latency_stretch` is 1.0

#### Scenario: Detour
- **WHEN** the single flow of a scenario is delivered on a path of latency 4 and its healthy shortest latency is 2
- **THEN** `latency_stretch` is 2.0

### Requirement: Recovery ratio
`recovery_ratio` SHALL be delivered after the event over delivered before it, summed over affected flows, and SHALL be unset when there are no affected flows.

Expected values: worked from the definitions in PLAN.md section 8, not from code; the owner confirms them by hand before the test is written.

#### Scenario: Partial recovery
- **WHEN** affected flows delivered 20 before the event and 15 after
- **THEN** `recovery_ratio` is 0.75

#### Scenario: No affected flows
- **WHEN** an event affects no flow
- **THEN** `recovery_ratio` is unset

### Requirement: Churn
`churn_flows` SHALL be the number of flows whose path set changed from the previous allocation and `churn_rate` SHALL be the rate carried on the changed paths.

Expected values: worked from the definitions in PLAN.md section 8, not from code; the owner confirms them by hand before the test is written.

#### Scenario: One flow moved
- **WHEN** one flow of 10 Mbps moves to a different path and all others keep their paths
- **THEN** `churn_flows` is 1 and `churn_rate` is 10

### Requirement: P0 greedy gap
`p0_greedy_gap` SHALL be the sum of `greedy_gap` over P0 flows.

Source: PLAN.md section 8.

#### Scenario: No critical traffic lost to the heuristic
- **WHEN** every unserved P0 flow has `greedy_gap` 0
- **THEN** `p0_greedy_gap` is 0

### Requirement: Empty cases
Ratios with zero demand SHALL be reported as 1.0 and SHALL NOT raise.

Source: a design decision of this change (design.md); PLAN.md does not specify it.

#### Scenario: No flows
- **WHEN** metrics are computed for a scenario with no flows
- **THEN** `dr` is 1.0 and no error is raised
