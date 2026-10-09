# judge-kit Specification

## Purpose
Lets judges change a scenario (flows, priorities, failed links, load) and run it live with one command, as CommitCon rule 9.5 allows them to ask.

## Requirements

### Requirement: Example scenarios
`examples/` SHALL contain at least these scenario files:
- `custom-flow.json`: the campus template with one added P0 flow between two named buildings
- `custom-failure.json`: the campus template with an event list that fails three named links in one event, then recovers one of them
- `overload.json`: the campus template at load factor 1.5

Each file SHALL validate as a `Scenario` without any change to the cycle-1 contract.

Source: PLAN-CYCLE2.md section 3.0. PLAN.md section 7 (`Scenario`).

#### Scenario: Files validate
- **WHEN** every file in `examples/` is loaded with the cycle-1 scenario loader
- **THEN** each one loads without error

### Requirement: Every example runs under every policy
Each example SHALL run under S0, S0-QoS, S1 and S2 with `python -m cli run --scenario <file> --policy <name>` and exit with status 0. Every snapshot SHALL pass `check_invariants`; I4 applies to S1 and S2 only.

Source: PLAN.md section 9 (invariants), CommitCon rule 9.3 (the project must work during the demo).

#### Scenario: All examples, all policies
- **WHEN** the judge-kit test runs each example under each of the four policies
- **THEN** all 12 runs exit with status 0 and no invariant fails

### Requirement: Edits by hand are supported
Changing a flow's rate, class, source or destination, or a failed link id, in an example file SHALL take effect on the next run without any other change. An unknown node or link id SHALL be rejected with an error naming the id.

Source: cycle-1 change `add-simulation-engine` (unknown ids are rejected).

#### Scenario: Edited priority
- **WHEN** the added flow in `custom-flow.json` is changed from P0 to P2 and the file is run under S2
- **THEN** the run succeeds and the flow is reported with class 2

#### Scenario: Mistyped link id
- **WHEN** a failed link id in `custom-failure.json` is changed to an id that does not exist
- **THEN** the run exits non-zero and the error names that id
