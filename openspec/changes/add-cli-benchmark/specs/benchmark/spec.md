## ADDED Requirements

### Requirement: Seeded benchmark matrix
The benchmark SHALL generate, for each of 30 seeds, one campus network of the demo size with a failure set drawn from that seed, and SHALL run S0, S0-QoS, S1 and S2 on identical copies of each case.

Expected values: the counts and thresholds stated in PLAN.md section 9.

#### Scenario: All policies on every seed
- **WHEN** the benchmark runs with 30 seeds
- **THEN** the results contain every policy for every seed and case

#### Scenario: Identical conditions
- **WHEN** the results of two policies for the same seed and case are compared
- **THEN** both report the same total demand and the same failed links

#### Scenario: Benchmark is reproducible
- **WHEN** the benchmark is run twice with the same arguments
- **THEN** every metric column except compute time is identical

### Requirement: Load-factor sweep
The benchmark SHALL scale all demands by each factor in 0.5, 0.75, 1.0, 1.25, 1.5 and 2.0 and report `DR`, `DR_P1` and `DR_P0` per policy at each factor.

Expected values: the counts and thresholds stated in PLAN.md section 9.

#### Scenario: Six factors
- **WHEN** the benchmark completes
- **THEN** each policy has results at all six load factors

### Requirement: Ablations
The benchmark SHALL run S2 with each knob (ordering within class, `max_paths`, congestion lambda, utilization cap) changed one at a time on the same seeds.

Expected values: the counts and thresholds stated in PLAN.md section 9.

#### Scenario: One knob at a time
- **WHEN** an ablation variant is recorded
- **THEN** it differs from the default S2 config in exactly one knob

### Requirement: Results files
The benchmark SHALL write a CSV with one row per seed, case, load factor, policy and variant, holding every metric, and a summary file recording the configuration, the code version and any matrix reduction applied.

Expected values: the counts and thresholds stated in PLAN.md section 9.

#### Scenario: CSV written
- **WHEN** the benchmark completes
- **THEN** the CSV exists and every row has a value for every metric column

### Requirement: Summary statistics
The benchmark SHALL report the mean, the median and a 95% bootstrap confidence interval for each headline metric per policy, and for the per-seed difference between S2 and S0-QoS.

Expected values: the counts and thresholds stated in PLAN.md section 9.

#### Scenario: Interval is reproducible
- **WHEN** statistics are computed twice on the same CSV
- **THEN** the intervals are identical

### Requirement: Matrix sizing
The benchmark SHALL time the first seed and, if the full matrix is projected to exceed 30 minutes, reduce the ablations to `max_paths` and congestion lambda only, and SHALL record the reduction.

Expected values: the counts and thresholds stated in PLAN.md section 9.

#### Scenario: Projected overrun
- **WHEN** the first seed projects a total above 30 minutes
- **THEN** only the `max_paths` and lambda ablations are run and the summary says so

### Requirement: Hypothesis evaluation
The benchmark SHALL evaluate hypotheses H1, H1b, H2, H3, H4 and H5 of PLAN.md section 9 against S0-QoS and report each as passed or failed with its measured value. A failed hypothesis SHALL be reported, not omitted.

Expected values: the counts and thresholds stated in PLAN.md section 9.

#### Scenario: H1 passes
- **WHEN** the mean `DR` difference of S2 over S0-QoS in stress cases is at least 10 percentage points and its 95% interval is above zero
- **THEN** H1 is reported as passed with the mean and the interval

#### Scenario: H1 fails
- **WHEN** the mean difference is below 10 percentage points
- **THEN** H1 is reported as failed with the measured value

#### Scenario: H3 overloads
- **WHEN** results are evaluated
- **THEN** H3 reports the count of overload violations for S2 and for the baselines

#### Scenario: H5 lists exceptions
- **WHEN** some runs have a non-zero P0 greedy gap
- **THEN** H5 reports the share of runs with zero gap and lists the runs where it is not zero

### Requirement: Property tests over random scenarios
The test suite SHALL generate random topologies, flows and events from seeds and assert the invariants on every snapshot, for every policy, using the invariant checker.

Source: PLAN.md section 9.

#### Scenario: Random scenario passes
- **WHEN** a property test runs a generated scenario under S2
- **THEN** the invariant checker reports no violation on any snapshot

#### Scenario: Failure is replayable
- **WHEN** a property test fails
- **THEN** it reports the seed and parameters needed to replay the scenario from the CLI

### Requirement: Documented, reproducible deliverables
The README SHALL give the setup commands, the model and its assumptions, the algorithm, the architecture, how to reproduce a run from a seed, the benchmark results, and a limitations section listing cases where S2 ties or loses to S0-QoS and the single-pass baseline bias. A fallback run JSON SHALL be saved.

Source: PLAN.md section 15.

#### Scenario: Clean-machine setup
- **WHEN** the README setup steps are followed on a clean machine
- **THEN** one command starts the backend and one command starts the frontend
