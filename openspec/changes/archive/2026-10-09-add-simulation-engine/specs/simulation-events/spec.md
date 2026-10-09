## ADDED Requirements

### Requirement: Simulation lifecycle
A `Simulation` SHALL be created from a scenario, a policy and a config, and SHALL produce a step-0 snapshot of the healthy scenario. `reset()` SHALL restore the scenario's initial link states and return a snapshot equal to the original step-0 snapshot, apart from `metrics.compute_ms`.

Source: PLAN.md section 7.

#### Scenario: Step zero
- **WHEN** a simulation is created
- **THEN** a snapshot with step 0 is available with every flow routed by the policy

#### Scenario: Reset returns to step zero
- **WHEN** events are applied and then `reset()` is called
- **THEN** the returned snapshot equals the original step-0 snapshot, apart from `compute_ms`

### Requirement: Link failure and recovery
`apply(event)` SHALL set the named links to `down` for a `fail` event and to `up` for a `recover` event, recompute routes for all flows, and return a snapshot with the step incremented by one. A link failure SHALL take both of its arcs down.

Source: PLAN.md section 5.

#### Scenario: Fail a link
- **WHEN** a fail event names link BD on the diamond
- **THEN** the snapshot shows BD as `down` and no allocated path uses either arc of BD

#### Scenario: Recover a link
- **WHEN** link BD is failed and then recovered
- **THEN** the snapshot shows BD as `up`

### Requirement: Events are atomic
All links named in one event SHALL change state before routing runs, so that a simultaneous failure is one event with one snapshot.

Source: PLAN.md section 5.

#### Scenario: Three links in one event
- **WHEN** one fail event names three links
- **THEN** exactly one snapshot is produced and all three links are down in it

### Requirement: Node failure
A fail event naming a node SHALL fail every link incident to that node.

Source: PLAN.md section 2.

#### Scenario: Node failure isolates a host
- **WHEN** a fail event names a building switch
- **THEN** every link incident to it is down and flows to that building are unserved with cause `DISCONNECTED`

### Requirement: Idempotent events
Failing a link that is already down, or recovering a link that is already up, SHALL leave the link state and the allocation unchanged.

Source: PLAN.md section 13.

#### Scenario: Fail twice
- **WHEN** the same link is failed in two consecutive events
- **THEN** the allocation after the second event equals the allocation after the first

### Requirement: Full recompute on every event
Every event SHALL trigger a full recompute by the policy. The resulting allocation SHALL depend only on the current link states, the flows, the policy and the config.

Source: PLAN.md section 5 and 9 (scenarios 3 and 8).

#### Scenario: Simultaneous equals sequential
- **WHEN** three links are failed in one event, and in another run the same three links are failed in three events
- **THEN** the final link states, allocations and metrics are equal, apart from `compute_ms` and the measures of the last event (`recovery_ratio`, `churn_flows`, `churn_rate`); `affected_flows` and the event fields of the decision records (`step`, `failed_links`, `previous`) describe the event and may differ

#### Scenario: Recovery restores the original allocation
- **WHEN** a link is failed and then recovered
- **THEN** the allocation equals the step-0 allocation

### Requirement: Affected flows
The snapshot SHALL list the flows that had a path through a link that failed in this event, determined from the allocation before rerouting.

Source: PLAN.md section 8.

#### Scenario: Affected by a failure
- **WHEN** a link carrying flows F1 and F2 fails
- **THEN** `affected_flows` contains F1 and F2 and no flow that did not use the link

#### Scenario: Recovery affects no flow
- **WHEN** a recover event is applied
- **THEN** `affected_flows` is empty

### Requirement: Snapshot content
Each snapshot SHALL contain the step, the state of every link, the allocation, the metrics, the affected flows and the decision records of that step.

Source: PLAN.md section 7.

#### Scenario: Snapshot is complete
- **WHEN** an event is applied
- **THEN** the returned snapshot validates against the `Snapshot` model and has one decision record per flow

### Requirement: Unknown ids are rejected
An event naming a link or node that is not in the topology SHALL raise an error and SHALL NOT change any state.

Source: a design decision of this change (design.md); PLAN.md does not specify it.

#### Scenario: Unknown link
- **WHEN** a fail event names a link id that does not exist
- **THEN** an error is raised and the step and link states are unchanged

### Requirement: Optional invariant checking
When invariant checking is enabled, the simulation SHALL run the invariant checker on every snapshot and raise an error naming the violated invariant.

Source: PLAN.md section 5.

#### Scenario: Checking enabled in tests
- **WHEN** a simulation runs with checking enabled and a snapshot violates an invariant
- **THEN** an error naming that invariant is raised
