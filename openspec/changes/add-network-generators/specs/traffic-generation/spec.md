## ADDED Requirements

### Requirement: Seeded traffic generator
The system SHALL generate flows from `{generator, n_flows, load_factor, class_mix, seed}` on a given topology. Each flow SHALL have a unique id, an integer rate of at least 1, a class in the configured ordered class list, and distinct source and destination nodes that exist in the topology. The same parameters and topology SHALL always produce identical flows.

Expected values: the class counts are worked by arithmetic from the stated mix (10%, 40% and 50% of 200); the owner confirms them by hand before the test is written. Source: PLAN.md section 7.

#### Scenario: Same seed, same flows
- **WHEN** the generator is run twice with the same parameters on the same topology
- **THEN** the two flow lists are identical

#### Scenario: Requested flow count
- **WHEN** `n_flows` is 200
- **THEN** 200 flows are returned with unique ids

#### Scenario: Class mix is respected
- **WHEN** `class_mix` gives P0 10%, P1 40%, P2 50% and `n_flows` is 200
- **THEN** the flows contain 20 P0, 80 P1 and 100 P2 flows

### Requirement: Critical flows target key services
Generated P0 flows SHALL have a key-service node (for example auth or emergency) as source or destination, and SHALL carry a `service` label.

Source: PLAN.md section 2 and 10.

#### Scenario: P0 flow is labelled
- **WHEN** traffic is generated on the campus template
- **THEN** every P0 flow has a non-empty `service` and one endpoint that is a key-service node

### Requirement: Explicit traffic list
A `TrafficSpec` containing an explicit list of flows SHALL be used as given, without randomness.

Source: PLAN.md section 7.

#### Scenario: Explicit flows pass through
- **WHEN** a traffic spec lists the two diamond flows
- **THEN** exactly those two flows are returned unchanged

### Requirement: Load-factor scaling
The system SHALL scale the demands of a flow list by a load factor, keeping flow ids, endpoints and classes unchanged and keeping every rate an integer of at least 1.

Source: PLAN.md section 9.

#### Scenario: Scaling keeps the flow set
- **WHEN** a flow list is scaled by 1.5
- **THEN** the result has the same flow ids, endpoints and classes, and every rate is an integer

#### Scenario: Scaling by one is the identity
- **WHEN** a flow list is scaled by 1.0
- **THEN** the result equals the input
