## ADDED Requirements

### Requirement: Shared typed contract
The system SHALL define every model named in PLAN.md section 7 as a pydantic v2 model in `core/model/types.py`: `Node`, `Link`, `Topology`, `Flow`, `PathAlloc`, `FlowResult`, `Allocation`, `PolicyConfig`, `Event`, `Attempt`, `CutArc`, `DecisionRecord`, `Metrics`, `TopologySpec`, `TrafficSpec`, `Scenario` and `Snapshot`, with the fields and defaults stated there. The module SHALL also define the `RoutingPolicy` protocol.

Expected values: the field defaults stated in PLAN.md section 7.

#### Scenario: Every contract type is importable
- **WHEN** a test imports each model name listed above from `core.model.types`
- **THEN** every import succeeds and no model has a field typed `Any`

#### Scenario: Policy config defaults
- **WHEN** `PolicyConfig()` is created with no arguments
- **THEN** `order` is `"class_size_desc"`, `max_paths` is 3, `congestion_lambda` is 0 and `util_cap` is 1.0

#### Scenario: Unknown cause is rejected
- **WHEN** a `FlowResult` is built with a `cause` outside `NONE`, `DISCONNECTED`, `INSUFFICIENT_CAPACITY`, `PATH_LIMIT`, `OVERLOAD_LOSS`
- **THEN** validation fails

### Requirement: Integer inputs and float deliveries
Link capacity, link latency, flow rate, path rate and arc load SHALL be integers. `delivered` and `unserved` on `FlowResult` and `DecisionRecord` SHALL be floats, because S0 and S0-QoS deliveries are fractional.

Expected values: hand-worked, PLAN.md sections 2 and 4 (a 7 Mbps flow scaled by 0.4 delivers 2.8 and leaves 4.2 unserved).

#### Scenario: Fractional delivery validates
- **WHEN** an S0 snapshot fixture containing a flow with `delivered` 2.8 and `unserved` 4.2 is loaded
- **THEN** it validates as a `Snapshot` and the values are preserved

#### Scenario: Non-integer capacity is rejected
- **WHEN** a `Link` is built with `capacity` 10.5
- **THEN** validation fails

### Requirement: Directed arc model
Each physical link SHALL be represented as two directed arcs, one per direction, each with the link's capacity and latency. An arc id SHALL be `"<link id>:<from>><to>"`. An arc SHALL be available if and only if its link status is `up`.

Source: PLAN.md section 4 and 7.

#### Scenario: Link expands to two arcs
- **WHEN** a link `L7` between `B` and `D` with capacity 10 is expanded
- **THEN** the arcs `L7:B>D` and `L7:D>B` exist, each with capacity 10

#### Scenario: Down link has no available arcs
- **WHEN** a link has status `down`
- **THEN** neither of its arcs appears in the available arc set

#### Scenario: Arc order is deterministic
- **WHEN** the arc list of a topology is built twice
- **THEN** both lists are identical and sorted by arc id

### Requirement: Validating fixtures
The repository SHALL hold JSON fixtures under `fixtures/` that validate against the models: one snapshot per policy (S0, S0-QoS, S1, S2) for the diamond network, one S0 snapshot with a non-integer `delivered`, and the decision-record example from PLAN.md section 10.

Expected values: the decision-record fixture, copied from the example in PLAN.md section 10.

#### Scenario: Decision-record example validates
- **WHEN** the section 10 decision-record JSON is loaded as a `DecisionRecord`
- **THEN** it validates and `cut[0].load_by_class` equals `{0: 10}`

#### Scenario: All fixtures load
- **WHEN** the fixture test loads every file under `fixtures/`
- **THEN** each validates against its declared model

### Requirement: Shared agent instructions
The repository SHALL contain `AGENTS.md` at the root stating the stack, folder ownership, the determinism rules, the test command, and that `core/model/types.py` and `fixtures/` are never edited by an agent. `CLAUDE.md` SHALL point to it.

Source: PLAN.md section 11.

#### Scenario: Tool instruction file points to the shared file
- **WHEN** `CLAUDE.md` is read
- **THEN** it references `AGENTS.md` as the shared rules

### Requirement: Consistent topology ids
A `Topology` SHALL reject duplicate node ids, duplicate link ids, and links whose endpoints are not listed as nodes.

Source: added during implementation after a hand-written fixture repeated ids; confirmed by B.

#### Scenario: Duplicate link id is rejected
- **WHEN** a topology has two links with id `L1`
- **THEN** validation fails naming the duplicate id

#### Scenario: Link to an unknown node is rejected
- **WHEN** a link refers to node `D` and no node `D` is listed
- **THEN** validation fails naming `D`
