## ADDED Requirements

### Requirement: S0 shortest-path routing
S0 SHALL route each flow on its latency-shortest path over available arcs, with no capacity check and no priority. A flow with no path SHALL have no allocation and cause `DISCONNECTED`. `arc_load` SHALL be the offered load on each arc.

Expected values: hand-worked, PLAN.md section 4 (diamond table).

#### Scenario: Flows pile onto the shortest path
- **WHEN** S0 routes the two diamond flows on the healthy diamond
- **THEN** both flows are on A-B-D and the load on arcs A>B and B>D is 25

#### Scenario: Disconnected flow
- **WHEN** a flow's destination is unreachable
- **THEN** the flow has no paths, delivered 0 and cause `DISCONNECTED`

### Requirement: S0 proportional delivery
S0 delivery SHALL be `rate * min over arcs on the path of min(1, capacity / load)`. A flow that loses traffic SHALL have cause `OVERLOAD_LOSS`.

Expected values: hand-worked, PLAN.md section 4 (diamond table). The non-integer case (2.8 of 7) is the fixture named at the end of section 4.

#### Scenario: Healthy diamond
- **WHEN** S0 routes F1 (P0, 15) and F2 (P2, 10) from A to D on the healthy diamond
- **THEN** F1 delivers 6 and F2 delivers 4, both with cause `OVERLOAD_LOSS`

#### Scenario: Diamond with BD failed
- **WHEN** link BD is down
- **THEN** both flows are on A-C-D, F1 delivers 6 and F2 delivers 4

#### Scenario: Non-integer delivery
- **WHEN** a 7 Mbps flow is on a path whose worst arc has scale 0.4
- **THEN** it delivers 2.8 and has 4.2 unserved, within a tolerance of 1e-9

#### Scenario: No overload
- **WHEN** no arc on a flow's path is loaded above capacity
- **THEN** the flow delivers its full rate with cause `NONE`

### Requirement: S0-QoS strict-priority delivery
S0-QoS SHALL use exactly the routes and offered load of S0. On each arc, class k SHALL be given `max(0, capacity − load of all higher classes)`, with scale `1` when class k has no load on the arc and `min(1, available / load of class k)` otherwise. A flow's delivery SHALL be its rate times the minimum scale of its class over the arcs of its path.

Expected values: hand-worked, PLAN.md section 4 (diamond table). The scale-factor rule is the pseudocode in section 5.

#### Scenario: Same routes as S0
- **WHEN** S0 and S0-QoS route the same flows on the same topology
- **THEN** every flow has the same path and `arc_load` is identical

#### Scenario: Healthy diamond
- **WHEN** S0-QoS routes the two diamond flows on the healthy diamond
- **THEN** F1 delivers 10 and F2 delivers 0

#### Scenario: Diamond with BD failed
- **WHEN** link BD is down
- **THEN** F1 delivers 10 and F2 delivers 0, on A-C-D

#### Scenario: Higher class is unaffected by lower classes
- **WHEN** all P2 flows are removed from a scenario
- **THEN** every P0 and P1 delivery under S0-QoS is unchanged

### Requirement: Baseline policies are pure and deterministic
S0 and S0-QoS SHALL process flows sorted by id and SHALL return identical output for identical input.

Source: PLAN.md section 7.

#### Scenario: Repeat run
- **WHEN** a baseline routes the same input twice
- **THEN** the two allocations are equal
