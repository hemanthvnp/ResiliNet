## ADDED Requirements

### Requirement: List scenarios
`GET /scenarios` SHALL return the built-in scenarios with an id and a name for each.

Source: PLAN.md section 7.

#### Scenario: Built-in scenarios listed
- **WHEN** a client calls `GET /scenarios`
- **THEN** the response is 200 and includes the eight fixture scenarios

### Requirement: Create a run
`POST /runs` SHALL accept a scenario id or an inline scenario, a policy name and an optional config, create a session, and return a run id, the resolved scenario, topology and flows, and the step-0 snapshot.

Source: PLAN.md section 7.

#### Scenario: Run from a built-in scenario
- **WHEN** a client posts `{scenario_id: "diamond", policy: "S2"}`
- **THEN** the response is 200 with a run id and a snapshot whose step is 0

#### Scenario: Run from a generator spec
- **WHEN** a client posts an inline scenario with a campus generator spec and a seed
- **THEN** the response contains the generated topology and flows, and the same request returns the same topology again

#### Scenario: Unknown policy
- **WHEN** a client posts a policy name that is not registered
- **THEN** the response is 422 and names the policy

#### Scenario: Unknown scenario
- **WHEN** a client posts a `scenario_id` that does not exist
- **THEN** the response is 404

### Requirement: Apply an event
`POST /runs/{id}/events` SHALL apply a fail or recover event to the run and return the new snapshot.

Source: PLAN.md section 7.

#### Scenario: Fail a link
- **WHEN** a client posts `{kind: "fail", links: ["L3"]}` to an existing run
- **THEN** the response is 200 with a snapshot one step later in which L3 is down

#### Scenario: Unknown run
- **WHEN** a client posts an event to a run id that does not exist
- **THEN** the response is 404

#### Scenario: Unknown link
- **WHEN** a client posts an event naming a link that is not in the topology
- **THEN** the response is 422 and the run's state is unchanged

### Requirement: Reset a run
`POST /runs/{id}/reset` SHALL return the run to step 0 with the same seed and return the step-0 snapshot.

Source: PLAN.md section 7.

#### Scenario: Reset after events
- **WHEN** a client applies events and then resets
- **THEN** the returned snapshot equals the run's original step-0 snapshot, apart from `compute_ms`

### Requirement: Compare policies
`POST /compare` SHALL run every requested policy on identical copies of the scenario and return the resolved scenario, topology and flows, a table of headline metrics per policy and the snapshots of each policy.

Expected values: hand-worked, PLAN.md section 4 (diamond table).

#### Scenario: Four policies
- **WHEN** a client posts the diamond scenario with policies S0, S0-QoS, S1 and S2
- **THEN** the response has one table row and one snapshot sequence per policy, and the S2 row reports 0 overloaded arcs

#### Scenario: Identical conditions
- **WHEN** a comparison is requested for a generator scenario
- **THEN** every policy's snapshots show the same links, flows and events

### Requirement: Flow decision record
`GET /runs/{id}/flows/{flow_id}/decision` SHALL return the decision record of that flow at the run's current step.

Source: PLAN.md section 7.

#### Scenario: Decision for an unserved flow
- **WHEN** a client requests the decision for a flow that is unserved under S2
- **THEN** the response is a decision record with a cause, a max-flow bound, a greedy gap and an explanation

#### Scenario: Unknown flow
- **WHEN** a client requests a flow id that is not in the run
- **THEN** the response is 404

### Requirement: Mock mode
The API SHALL have a mock mode in which the same endpoints return fixture snapshots, with the same routes, schemas and status codes as live mode.

Source: PLAN.md section 11 and 12.

#### Scenario: Mocked run
- **WHEN** the API runs in mock mode and a client posts to `/runs`
- **THEN** the response validates against the same schema as a live response

### Requirement: OpenAPI contract
The API SHALL expose an OpenAPI schema generated from the shared models, and the committed schema file SHALL match the generated one.

Source: PLAN.md section 11.

#### Scenario: Schema is current
- **WHEN** the schema test compares the committed schema file with the generated schema
- **THEN** they are equal

### Requirement: Thin API layer
The API package SHALL contain no routing, simulation or metric logic, and the core library SHALL NOT import FastAPI.

Source: PLAN.md section 6.

#### Scenario: Core has no web imports
- **WHEN** the modules under `core/` are inspected
- **THEN** none imports `fastapi` or anything from `api/`

### Requirement: Session isolation
Each run SHALL have its own simulation state. Events on one run SHALL NOT change another run.

Source: PLAN.md section 6.

#### Scenario: Two runs
- **WHEN** a link is failed in one run
- **THEN** the same link is still up in a second run of the same scenario
