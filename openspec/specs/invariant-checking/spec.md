# invariant-checking Specification

## Purpose
TBD - created by archiving change add-metrics-invariants. Update Purpose after archive.

## Requirements

### Requirement: Invariant checker
`check_invariants` SHALL examine a snapshot with its topology and flows and report every violated invariant by its id (I1 to I11). It SHALL NOT use the routing policies or their ledger to do so.

Source: PLAN.md section 9, invariant table. The inputs in the scenarios are illustrative cases chosen by hand.

#### Scenario: Valid snapshot
- **WHEN** a correct snapshot is checked
- **THEN** no violation is reported

#### Scenario: Violation is named
- **WHEN** a snapshot with a path through a down arc is checked
- **THEN** a violation with id `I1` is reported

### Requirement: Path validity (I1, I2)
No allocated path SHALL contain a down arc, and every path SHALL be a simple path from the flow's source to its destination.

Source: PLAN.md section 9, invariant table. The inputs in the scenarios are illustrative cases chosen by hand.

#### Scenario: Repeated node
- **WHEN** a snapshot contains a path that visits a node twice
- **THEN** `I2` is reported

### Requirement: Demand accounting (I3)
For every flow, `delivered` SHALL not exceed demand and `delivered + unserved` SHALL equal demand, within a tolerance of 1e-9.

Source: PLAN.md section 9, invariant table. The inputs in the scenarios are illustrative cases chosen by hand.

#### Scenario: Fractional baseline delivery passes
- **WHEN** a flow of 7 has delivered 2.8 and unserved 4.2
- **THEN** no violation is reported

#### Scenario: Over-delivery
- **WHEN** a flow of 10 has delivered 11
- **THEN** `I3` is reported

### Requirement: Capacity (I4)
For S1 and S2, the load on every arc SHALL not exceed `floor(util_cap × capacity)`. The check SHALL NOT be applied to S0 and S0-QoS.

Source: PLAN.md section 9, invariant table. The inputs in the scenarios are illustrative cases chosen by hand.

#### Scenario: Overloaded arc under S2
- **WHEN** an S2 snapshot has an arc of capacity 10 with load 11
- **THEN** `I4` is reported

#### Scenario: Overloaded arc under S0
- **WHEN** an S0 snapshot has an arc of capacity 10 with load 25
- **THEN** `I4` is not reported

### Requirement: Load consistency (I5, I6)
`arc_load` SHALL equal the sum of path rates through each arc. Ledger reserve and release SHALL be symmetric: after all allocations are released, every residual equals capacity.

Source: PLAN.md section 9, invariant table. The inputs in the scenarios are illustrative cases chosen by hand.

#### Scenario: Load mismatch
- **WHEN** `arc_load` for an arc differs from the sum of path rates through it
- **THEN** `I6` is reported

### Requirement: Cause correctness (I7)
Every flow with unserved demand SHALL have a cause other than `NONE`. `DISCONNECTED` SHALL be accepted only when source and destination are in different components of the available graph. `INSUFFICIENT_CAPACITY` SHALL be accepted only when a path exists in the available graph.

Source: PLAN.md section 9, invariant table. The inputs in the scenarios are illustrative cases chosen by hand.

#### Scenario: False disconnection
- **WHEN** a flow is marked `DISCONNECTED` but a path of available arcs exists
- **THEN** `I7` is reported

#### Scenario: Missing cause
- **WHEN** a flow has unserved demand and cause `NONE`
- **THEN** `I7` is reported

### Requirement: Determinism (I8)
The system SHALL provide a comparison that reports whether two snapshot sequences are byte-identical once `metrics.compute_ms` is masked.

Source: PLAN.md section 9, invariant table. The inputs in the scenarios are illustrative cases chosen by hand.

#### Scenario: Only compute time differs
- **WHEN** two sequences differ only in `compute_ms`
- **THEN** they are reported as identical

### Requirement: Metric consistency (I9)
Metrics recomputed from the snapshot's allocation SHALL equal the reported metrics.

Source: PLAN.md section 9, invariant table. The inputs in the scenarios are illustrative cases chosen by hand.

#### Scenario: Tampered metric
- **WHEN** a snapshot's `dr` is altered
- **THEN** `I9` is reported

### Requirement: Class isolation (I10)
The system SHALL provide a check that, for S2, routing with all lower-class flows removed leaves a class's allocation unchanged.

Source: PLAN.md section 9, invariant table. The inputs in the scenarios are illustrative cases chosen by hand.

#### Scenario: Isolation holds
- **WHEN** the check is run on a scenario under S2
- **THEN** P0 allocations with and without P1 and P2 flows are equal

### Requirement: Explanation consistency (I11)
For every unserved S1/S2 flow, `greedy_gap` SHALL be at least 0, and `cut` SHALL be non-empty only when the cause is `INSUFFICIENT_CAPACITY`.

Source: PLAN.md section 9, invariant table. The inputs in the scenarios are illustrative cases chosen by hand.

#### Scenario: Cut under path limit
- **WHEN** a record with cause `PATH_LIMIT` has a non-empty cut
- **THEN** `I11` is reported

#### Scenario: Negative gap
- **WHEN** a record has `greedy_gap` below 0
- **THEN** `I11` is reported
