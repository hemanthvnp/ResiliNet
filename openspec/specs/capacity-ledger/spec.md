# capacity-ledger Specification

## Purpose
TBD - created by archiving change add-core-model-contract. Update Purpose after archive.

## Requirements

### Requirement: Residual capacity accounting
`Ledger` SHALL be created from the available arcs of a topology with effective capacity `floor(util_cap * capacity)` per arc and zero load. `residual(arc)` SHALL return effective capacity minus load, and SHALL never be negative.

Expected values: worked from the definitions in PLAN.md section 4 (effective capacity is floor(util_cap x capacity), so floor(0.9 x 15) = 13), not from code; the owner confirms them by hand before the test is written.

#### Scenario: Fresh ledger
- **WHEN** a ledger is created for an arc of capacity 10 with `util_cap` 1.0
- **THEN** `residual` of that arc is 10

#### Scenario: Utilization cap reduces capacity
- **WHEN** a ledger is created for an arc of capacity 15 with `util_cap` 0.9
- **THEN** `residual` of that arc is 13

#### Scenario: Down arcs are excluded
- **WHEN** a ledger is created from a topology with a down link
- **THEN** the arcs of that link are not in the ledger

### Requirement: Reservation never exceeds capacity
`reserve(path, rate, cls)` SHALL add `rate` to the load of every arc on the path and record it against class `cls`. It SHALL raise an error, and change nothing, if any arc on the path has residual below `rate`.

Expected values: worked from the definitions in PLAN.md section 4 and 7, not from code; the owner confirms them by hand before the test is written.

#### Scenario: Reservation within capacity
- **WHEN** 6 is reserved on a path whose arcs each have residual 10
- **THEN** each arc's residual is 4

#### Scenario: Reservation beyond capacity raises
- **WHEN** 11 is reserved on a path containing an arc with residual 10
- **THEN** an error is raised and no arc's residual has changed

### Requirement: Bottleneck of a path
`bottleneck(path)` SHALL return the minimum residual over the arcs of the path.

Expected values: worked from the definitions in PLAN.md section 4 and 7, not from code; the owner confirms them by hand before the test is written.

#### Scenario: Bottleneck is the tightest arc
- **WHEN** a path has arcs with residuals 10, 3 and 7
- **THEN** `bottleneck` returns 3

### Requirement: Symmetric release
`release(path, rate, cls)` SHALL subtract `rate` from every arc on the path and from that class's recorded load. After every reservation has been released, every residual SHALL equal the effective capacity.

Expected values: worked from the definitions in PLAN.md section 4 and 7, not from code; the owner confirms them by hand before the test is written.

#### Scenario: Release restores capacity
- **WHEN** 6 is reserved on a path and then 6 is released on the same path
- **THEN** every arc's residual equals its effective capacity

### Requirement: Per-class load breakdown
`class_breakdown(arcs)` SHALL return, for the given arcs, the load held by each class, so that a cut can be attributed to the classes occupying it.

Expected values: worked from the definitions in PLAN.md section 4 and 7, not from code; the owner confirms them by hand before the test is written.

#### Scenario: Breakdown by class
- **WHEN** class 0 holds 10 and class 2 holds 5 on an arc
- **THEN** `class_breakdown` for that arc reports `{0: 10, 2: 5}`
