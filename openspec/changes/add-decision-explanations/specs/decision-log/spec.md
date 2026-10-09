## ADDED Requirements

### Requirement: One decision record per flow per event
Every policy SHALL return one `DecisionRecord` for every flow on every routing call, carrying the flow id, class, demand, step, delivered, unserved, cause and explanation. Records SHALL be ordered deterministically.

Source: PLAN.md section 7 and 10.

#### Scenario: Record count
- **WHEN** a policy routes 200 flows
- **THEN** it returns 200 decision records with unique flow ids

#### Scenario: Baseline record
- **WHEN** S0 or S0-QoS routes a flow
- **THEN** the record has an empty `attempts` list, an empty `cut`, and `maxflow_bound` and `greedy_gap` unset

### Requirement: Reference path and status
Each record SHALL hold the latency-shortest path over available arcs, ignoring capacity, and a status stating whether it was used in full, used in part with the arc where residual ran out, or absent because the flow is disconnected. When a flow's previous path crosses a newly failed link, the record SHALL list the previous paths and name the failed link.

Expected values: the decision-record example in PLAN.md section 10.

#### Scenario: Previous path invalidated
- **WHEN** a flow's previous path used link L7 and L7 has failed
- **THEN** `previous` holds that path, `failed_links` contains `L7`, and the status says the path is invalid because L7 is down

#### Scenario: Reference path only partly usable
- **WHEN** a flow needs 15 and its reference path has bottleneck 10
- **THEN** the status names the saturated arc on the reference path

### Requirement: Attempts are logged
For S1 and S2, each push SHALL be recorded as an `Attempt` with its iteration, arcs, cost, latency, bottleneck and amount pushed. The amounts pushed SHALL sum to the flow's delivered rate.

Expected values: hand-worked, PLAN.md section 4 (diamond table).

#### Scenario: Two pushes
- **WHEN** S2 places F1 (15 Mbps) on the healthy diamond
- **THEN** the record has two attempts, pushing 10 on A-B-D and 5 on A-C-D

### Requirement: Residual cut for insufficient capacity
When the cause is `INSUFFICIENT_CAPACITY`, the record SHALL hold the cut: the arcs from a node reachable from the source over positive-residual arcs to a node that is not, each marked `saturated` or `down`, with the load held on it by class. The cut SHALL be empty for every other cause.

Expected values: hand-worked, the decision-record example in PLAN.md section 10 (the section 4 diamond with BD down).

#### Scenario: Cut after BD fails
- **WHEN** S2 places F1 (P0, 15) on the diamond with BD down
- **THEN** the cut contains the saturated arc on A-C-D with class 0 holding 10, and the down arc of BD

#### Scenario: No cut under path limit
- **WHEN** a flow is unserved with cause `PATH_LIMIT`
- **THEN** its `cut` is empty

### Requirement: Max-flow bound and greedy gap
For every unserved S1/S2 flow, `maxflow_bound` SHALL be `min(demand, max-flow from source to destination)` on the residual capacities as they were before the flow was placed, and `greedy_gap` SHALL be `maxflow_bound − delivered`. `greedy_gap` SHALL never be negative.

Expected values: bound 10 and gap 0 are in the PLAN.md section 10 example. The path-limit values (15 and 5) are worked from the section 5 formula, not from code; the owner confirms them by hand before the test is written.

#### Scenario: Shortfall is physical
- **WHEN** S2 places F1 (15 Mbps) on the diamond with BD down
- **THEN** `maxflow_bound` is 10 and `greedy_gap` is 0

#### Scenario: Shortfall is the heuristic's
- **WHEN** a flow is placed on the blocking example where shortest-path pushes deliver less than max-flow
- **THEN** `greedy_gap` is greater than 0

#### Scenario: Path limit gap
- **WHEN** `max_paths` is 1 and F1 (15 Mbps) is placed on the healthy diamond
- **THEN** `maxflow_bound` is 15 and `greedy_gap` is 5

### Requirement: Templated one-line explanation
The `explanation` SHALL be generated from the record's fields by a fixed template. When `greedy_gap` is 0 and a cut exists it SHALL name the cut and the classes saturating it. When `greedy_gap` is greater than 0 it SHALL state how much could have been routed and SHALL NOT present the cut as a physical limit.

Expected values: the explanation line in PLAN.md section 10, verbatim.

#### Scenario: Section 10 example
- **WHEN** the explanation is generated for the section 10 decision-record fixture
- **THEN** it equals `F12 (P0, 15 Mbps): path A-B-D invalid (L7 down). Moved 10 Mbps to A-C-D (latency 4 ms). 5 Mbps unserved: cut L5 saturated by P0 (10 Mbps).`

#### Scenario: Heuristic shortfall wording
- **WHEN** a record has 5 unserved and `greedy_gap` 5
- **THEN** the explanation says 5 Mbps unserved, of which 5 Mbps could have been routed (heuristic or path limit)

#### Scenario: Disconnected wording
- **WHEN** a record has cause `DISCONNECTED`
- **THEN** the explanation states the destination is unreachable and names no cut

#### Scenario: Same record, same text
- **WHEN** the explanation is generated twice from the same record
- **THEN** the two strings are identical

### Requirement: Lazy bound computation
The system SHALL be able to compute `maxflow_bound` and `greedy_gap` for one flow on request, by replaying the allocation up to that flow, and the result SHALL equal the value computed at route time.

Source: PLAN.md section 12 (cut lines).

#### Scenario: Lazy equals eager
- **WHEN** the bound for an unserved flow is computed at route time and again by replay
- **THEN** both values are equal
