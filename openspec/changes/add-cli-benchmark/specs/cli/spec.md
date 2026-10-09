## ADDED Requirements

### Requirement: Run a scenario from the command line
The CLI SHALL run a scenario, given as a file or a built-in id, under a named policy and SHALL write the snapshot sequence as JSON and print the headline metrics per step.

Source: PLAN.md section 6.

#### Scenario: Run the diamond under S2
- **WHEN** the run command is given the diamond scenario and policy `S2`
- **THEN** it exits with status 0 and the output JSON validates as a list of snapshots

#### Scenario: Unknown policy
- **WHEN** the run command is given a policy name that is not registered
- **THEN** it exits with a non-zero status and names the policy

### Requirement: Compare policies from the command line
The CLI SHALL run several policies on identical copies of one scenario and print one row of headline metrics per policy. With no policy list it SHALL use S0, S0-QoS, S1 and S2.

Expected values: hand-worked, PLAN.md section 4 (diamond table).

#### Scenario: Default comparison
- **WHEN** the compare command is given the diamond scenario and no policy list
- **THEN** four rows are printed and the S2 row shows `DR` 0.80 and 0 overloaded arcs for the healthy step

### Requirement: Policy configuration from flags
The CLI SHALL accept the ordering policy, `max_paths`, congestion lambda and utilization cap as options and pass them to the policy.

Expected values: worked from the definitions in PLAN.md section 5 (the pseudocode run on the section 4 diamond with max_paths 1), not from code; the owner confirms them by hand before the test is written.

#### Scenario: Path limit flag
- **WHEN** the run command is given the diamond scenario, policy `S2` and a path limit of 1
- **THEN** flow F1 is reported with cause `PATH_LIMIT`

### Requirement: Reproducible from a seed
The CLI SHALL accept a generator scenario with a seed, and two invocations with the same arguments SHALL write identical output apart from `compute_ms`.

Source: PLAN.md section 7 and 9.

#### Scenario: Same seed twice
- **WHEN** the run command is invoked twice with the same generator spec and seed
- **THEN** the two output files are identical once `compute_ms` is masked

### Requirement: No web dependency
The CLI SHALL work without the API server running and SHALL NOT import the API package.

Source: PLAN.md section 6.

#### Scenario: Server not running
- **WHEN** the run command is invoked with no server running
- **THEN** it completes normally
