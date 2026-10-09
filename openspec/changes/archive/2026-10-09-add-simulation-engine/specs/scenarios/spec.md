## ADDED Requirements

### Requirement: Scenario loading
The system SHALL build a ready simulation from a `Scenario` given as a JSON file or as an inline object, resolving its topology spec and traffic spec to a concrete topology and flow list. A scenario whose flows reference unknown nodes SHALL be rejected.

Source: PLAN.md section 7.

#### Scenario: Load a fixture file
- **WHEN** the diamond scenario file is loaded
- **THEN** a simulation exists with the diamond topology and its two flows

#### Scenario: Generator spec
- **WHEN** a scenario with a campus generator spec and a seed is loaded
- **THEN** the topology and flows are those the generators produce for that seed

#### Scenario: Flow with unknown node
- **WHEN** a scenario has a flow whose source is not a node of the topology
- **THEN** loading fails with an error naming the flow

### Requirement: Scenario run
The system SHALL run a scenario by applying its events in step order and SHALL return the full sequence of snapshots, starting with step 0.

Source: PLAN.md section 9.

#### Scenario: Snapshot sequence
- **WHEN** a scenario with two events is run
- **THEN** three snapshots are returned, with steps 0, 1 and 2

### Requirement: Identical conditions across policies
When one scenario is run under several policies, each policy SHALL receive its own deep copy of the same topology, flows and events.

Source: PLAN.md section 9.

#### Scenario: One policy cannot affect another
- **WHEN** a scenario is run under S0 and then under S2
- **THEN** the S2 result equals the result of running S2 alone

### Requirement: Reproducible runs
The same scenario, policy, config and seed SHALL produce a byte-identical serialized snapshot sequence once `metrics.compute_ms` is masked.

Source: PLAN.md section 9 (invariant I8).

#### Scenario: Two runs compared
- **WHEN** a scenario is run twice and both sequences are serialized with `compute_ms` masked
- **THEN** the two outputs are byte-identical

### Requirement: Scenario fixtures
The repository SHALL hold the eight scenarios of PLAN.md section 9 as JSON files with assertions: normal operation, single critical-link failure, multiple simultaneous failures, congestion on alternatives, insufficient capacity, disconnected destination, critical against ordinary traffic (diamond), and link recovery.

Expected values: hand-worked, PLAN.md section 4 (diamond table) and the scenario table in section 9. Each fixture's `expect` block is written by the owner before the code runs.

#### Scenario: Diamond fixture
- **WHEN** scenario 7 is run under S0, S0-QoS and S2
- **THEN** every delivery equals the hand-worked value in the PLAN.md section 4 table

#### Scenario: Insufficient capacity fixture
- **WHEN** scenario 5 is run under S2
- **THEN** unserved demand is reported with cause `INSUFFICIENT_CAPACITY` and a cut, and P2 loses before P1 and P0

#### Scenario: Disconnected fixture
- **WHEN** scenario 6 is run under S2
- **THEN** flows to the isolated hostel have cause `DISCONNECTED`

#### Scenario: Recovery fixture
- **WHEN** scenario 8 is run
- **THEN** the allocation after recovery equals the step-0 allocation

#### Scenario: Normal operation fixture
- **WHEN** scenario 1 is run under S2
- **THEN** no arc is loaded above capacity
