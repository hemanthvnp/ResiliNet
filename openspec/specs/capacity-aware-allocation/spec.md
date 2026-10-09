# capacity-aware-allocation Specification

## Purpose
TBD - created by archiving change add-routing-policies. Update Purpose after archive.
## Requirements
### Requirement: Residual-graph allocation
The allocator SHALL start every call from an empty ledger over available arcs and place flows one at a time. For each flow it SHALL repeatedly find the least-cost path over arcs with residual above zero, push `min(remaining demand, path bottleneck)`, and reserve it, until the demand is met, no path remains, or `max_paths` paths are in use.

Expected values: hand-worked, PLAN.md section 4 (diamond table).

#### Scenario: Flow split over two paths
- **WHEN** S2 (`max_paths` 3, `util_cap` 1) places F1 (P0, 15) on the healthy diamond
- **THEN** F1 has 10 on A-B-D and 5 on A-C-D and delivers 15

#### Scenario: Healthy diamond, both flows
- **WHEN** S2 places F1 (P0, 15) and F2 (P2, 10) on the healthy diamond
- **THEN** F2 has 5 on A-C-D, 5 unserved with cause `INSUFFICIENT_CAPACITY`, and no arc is loaded above capacity

#### Scenario: Diamond with BD failed
- **WHEN** link BD is down
- **THEN** F1 has 10 on A-C-D and 5 unserved, and F2 has 10 unserved

### Requirement: Hard constraints
For S1 and S2, every allocated path SHALL be a simple path of available arcs from the flow's source to its destination, the total rate of a flow SHALL not exceed its demand, the load on every arc SHALL not exceed `floor(util_cap * capacity)`, and a flow SHALL use at most `max_paths` distinct paths.

Expected values: worked from the definitions in PLAN.md section 4 (floor(0.9 x 10) = 9), not from code; the owner confirms them by hand before the test is written.

#### Scenario: Capacity is never exceeded
- **WHEN** S2 routes a scenario whose demand exceeds network capacity
- **THEN** `arc_load` on every arc is at most its effective capacity

#### Scenario: Utilization cap
- **WHEN** `util_cap` is 0.9 and an arc has capacity 10
- **THEN** the load on that arc never exceeds 9

### Requirement: Ordering policy
With `order` `class_size_desc` or `class_size_asc`, flows SHALL be placed by class (P0 first), then by rate descending or ascending, then by flow id. With `order` `arrival`, flows SHALL be placed in input order regardless of class.

Source: PLAN.md section 5.

#### Scenario: Critical flow placed first
- **WHEN** a P2 flow precedes a P0 flow in the input and `order` is `class_size_desc`
- **THEN** the P0 flow is placed first

#### Scenario: Arrival order ignores class
- **WHEN** a P2 flow precedes a P0 flow in the input and `order` is `arrival`
- **THEN** the P2 flow is placed first

### Requirement: Class isolation
Under a class-first order, the allocation of each class SHALL be identical to the allocation it would receive if all lower classes did not exist.

Source: PLAN.md section 4.

#### Scenario: Removing lower classes changes nothing
- **WHEN** S2 routes a scenario, and routes it again with all P2 flows removed
- **THEN** every P0 and P1 flow has the same paths and rates in both runs

### Requirement: Cause of unserved demand
A flow whose source and destination are in different components of the available graph SHALL have cause `DISCONNECTED`. A flow with remaining demand SHALL have cause `PATH_LIMIT` if a path still exists over arcs with residual above zero, and `INSUFFICIENT_CAPACITY` otherwise. A fully served flow SHALL have cause `NONE`.

Expected values: worked from the definitions in PLAN.md section 5 (the pseudocode run on the section 4 diamond with max_paths 1: 10 delivered, 5 unserved), not from code; the owner confirms them by hand before the test is written.

#### Scenario: Disconnected destination
- **WHEN** a flow's destination is isolated by failures
- **THEN** the flow is unserved with cause `DISCONNECTED` and no path search is attempted

#### Scenario: Path limit reached
- **WHEN** `max_paths` is 1 and F1 (15 Mbps) is placed on the healthy diamond
- **THEN** F1 delivers 10 and has 5 unserved with cause `PATH_LIMIT`

### Requirement: Congestion-aware cost
Arc cost SHALL be `latency + congestion_lambda * (s(u) − 1)`, where `s(u)` is 1 for utilization below 1/3, 3 below 2/3, 10 below 0.9 and 70 otherwise. Costs SHALL be integers. With `congestion_lambda` 0 the cost SHALL equal latency.

Expected values: the slopes and thresholds stated in PLAN.md section 5.

#### Scenario: Lambda zero is pure latency
- **WHEN** `congestion_lambda` is 0
- **THEN** every arc cost equals its latency at any utilization

#### Scenario: Nearly full route is avoided
- **WHEN** two routes exist, the shorter is above 90% utilized, and `congestion_lambda` is greater than 0
- **THEN** the allocator chooses the longer, less loaded route

### Requirement: S1 and S2 are configurations of one allocator
S1 SHALL be the allocator with `order` `arrival`, `max_paths` 1 and `congestion_lambda` 0. S2 SHALL be the allocator with a class-first order and splitting enabled.

Source: PLAN.md section 1.

#### Scenario: S1 does not split
- **WHEN** S1 routes any scenario
- **THEN** every flow has at most one path

### Requirement: Purity and determinism
`route` SHALL be pure: no globals, clocks or unseeded randomness. The previous allocation SHALL NOT influence the result.

Source: PLAN.md section 7.

#### Scenario: Previous allocation is ignored
- **WHEN** S2 routes the same topology and flows with two different `prev` arguments
- **THEN** the two allocations are equal

### Requirement: Degenerate flows
A flow with `src == dst` SHALL be delivered in full with no path and no network load. A zero-rate flow SHALL have delivered 0, unserved 0 and cause `NONE`.

Source: PLAN.md section 13.

#### Scenario: Same source and destination
- **WHEN** a flow has `src` equal to `dst`
- **THEN** it is delivered in full and `arc_load` is unchanged

### Requirement: Policies registered by name
Policies SHALL be `RoutingPolicy` objects selectable by the names `S0`, `S0-QoS`, `S1` and `S2`. An unknown name SHALL raise an error. `route` SHALL accept an optional `step` keyword, written into every record, and SHALL reject duplicate flow ids, negative rates, `max_paths` below 1, a negative `congestion_lambda` and a `util_cap` outside (0, 1], because `PolicyConfig` checks only types. `arc_load` SHALL list every available arc, zero-load arcs included, and omit the arcs of down links.

Source: PLAN.md section 14.

#### Scenario: Lookup by name
- **WHEN** the registry is asked for `S0-QoS`
- **THEN** it returns the priority baseline policy

