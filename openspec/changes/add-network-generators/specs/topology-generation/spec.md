## ADDED Requirements

### Requirement: Campus template
The system SHALL provide a fixed campus template topology, selectable with `TopologySpec` `{template: "campus"}`, with a designated primary uplink and named key-service nodes.

Source: PLAN.md section 9 and 12.

#### Scenario: Template loads
- **WHEN** the spec `{template: "campus"}` is resolved
- **THEN** a valid `Topology` is returned with all links `up` and the same content on every call

### Requirement: Seeded campus generator
The system SHALL generate a campus topology from `{generator: "campus", buildings, redundancy, seed}` with integer capacities and latencies. The same parameters SHALL always produce an identical topology.

Source: PLAN.md section 7 and 9.

#### Scenario: Same seed, same network
- **WHEN** the generator is run twice with the same `buildings`, `redundancy` and `seed`
- **THEN** the two topologies serialize to identical JSON

#### Scenario: Different seed, different network
- **WHEN** the generator is run with two different seeds
- **THEN** the two topologies differ

#### Scenario: Generated network is connected
- **WHEN** a topology is generated
- **THEN** every node is reachable from every other node while all links are up

### Requirement: Post-failure path check
The system SHALL provide a check that, on a topology with its primary uplink failed, every building has at least two node-disjoint paths to the core whose combined capacity exceeds the P0 plus P1 demand of that building.

Source: PLAN.md section 9.

#### Scenario: Template passes after uplink failure
- **WHEN** the check is run on the campus template with its traffic and the primary uplink failed
- **THEN** it passes for every building

#### Scenario: Single remaining path fails the check
- **WHEN** the check is run on a network where a building has only one path to the core after the uplink failure
- **THEN** it fails and names that building

### Requirement: Generator retries on a failed check
The campus generator SHALL run the post-failure path check on its designated uplink and, on failure, retry with the next seed, at most 20 times, then raise an error. It SHALL report the seed that was actually used.

Expected values: the limit of 20 retries is stated in PLAN.md section 9.

#### Scenario: Retry reports the effective seed
- **WHEN** the requested seed fails the check and the next seed passes
- **THEN** the returned scenario records the passing seed

#### Scenario: Retries exhausted
- **WHEN** 20 consecutive seeds fail the check
- **THEN** the generator raises an error stating the last failure reason

### Requirement: Generators are registered by name
Topology and traffic generators SHALL be resolved by the name in the spec, so a new generator can be added without changing callers. An unknown name SHALL raise an error naming it.

Source: PLAN.md section 14.

#### Scenario: Unknown generator
- **WHEN** a spec names a generator that is not registered
- **THEN** resolution raises an error containing that name
