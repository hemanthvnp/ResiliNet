# Spec Delta

## Purpose

A single-link sensitivity analysis. It fails each link of one scenario in turn and reports which failures hurt delivery most and which disconnect part of the network, for each routing policy under identical conditions.

## ADDED Requirements

### Requirement: Fail every link once
For each policy, the sweep SHALL start from the scenario's healthy state: step 0, with every link up and the scenario's own events ignored. For each link, in ascending link-id order, it SHALL fail only that link and record the snapshot, then restore the healthy state before the next link. Every link SHALL appear exactly once per policy.

Expected values: hand-worked, PLAN.md section 4 (diamond, row "BD fails", generalised to each link). A human re-checks them before tests are written.

#### Scenario: Diamond under S2
- **WHEN** the sweep runs S2 on the diamond (F1 P0 15 Mbps, F2 P2 10 Mbps, A→D)
- **THEN** four rows are produced, one per link
- **AND** every row has post-failure `DR_P0` 0.667 (10 of 15), `DR` 0.40 (10 of 25) and 0 overloaded arcs
- **AND** every row has a `DR_P0` drop of 0.333 (from 1.00) and a `DR` drop of 0.40 (from 0.80)

#### Scenario: Diamond under S0-QoS
- **WHEN** the sweep runs S0-QoS on the diamond
- **THEN** every row has post-failure `DR_P0` 0.667, `DR` 0.40 and 2 overloaded arcs
- **AND** a `DR_P0` drop of 0 and a `DR` drop of 0, because healthy S0-QoS already delivers only 0.667 and 0.40

#### Scenario: Healthy state restored between links
- **WHEN** the sweep has processed any number of links
- **THEN** the step-0 snapshot taken again equals the original step-0 snapshot, apart from `compute_ms`

### Requirement: Structural and operational results
A link SHALL be in the `structural` group when failing it increases the number of connected components of the healthy topology (a bridge). Its row SHALL report the demand made unreachable (`DISCONNECTED`). All other links SHALL be in the `operational` group. Both groups SHALL appear in every output; neither is dropped.

Expected values: hand-worked from the definition.

#### Scenario: Single link between two nodes
- **WHEN** the sweep runs S2 on a two-node topology A–B (capacity 10, latency 1) with one P0 flow of 10 Mbps from A to B
- **THEN** link A–B is in the `structural` group with post-failure `DR_P0` 0 and unreachable demand 10

#### Scenario: No bridges in the diamond
- **WHEN** the sweep runs on the diamond
- **THEN** all four links are in the `operational` group

### Requirement: Ranking with shared ties
Within each policy and group, links SHALL be ranked by ascending post-failure `DR_P0`, then ascending post-failure `DR`. Rank 1 is the most damaging failure. Links equal on both values SHALL share the same rank, and the next rank SHALL skip accordingly (1, 1, 3). Link id SHALL only order rows within a shared rank.

Source: PLAN-CYCLE2.md sections 3.2 and 10 (C3.1).

#### Scenario: All tied on the diamond
- **WHEN** the sweep ranks the four diamond links under S2
- **THEN** all four have rank 1, and the rows are ordered by ascending link id

### Requirement: Output
The sweep SHALL write a CSV with one row per (policy, link). The columns are `policy, group, rank, link_id, dr_p0, dr, dr_p0_drop, dr_drop, overloaded_arcs, unreachable_demand`, where the drops are healthy value minus post-failure value for that policy. Rows SHALL be sorted by policy name, then group (`structural` before `operational`), then rank, then link id.

The sweep SHALL also print, per policy, every structural link and the top 5 operational ranks. With no policy list it SHALL run S2 and S0-QoS. Two runs with the same arguments SHALL write byte-identical CSV files.

Source: PLAN.md sections 7 and 9 (reproducibility). PLAN-CYCLE2.md section 10 (C3.2, C3.4).

#### Scenario: Default run
- **WHEN** `python -m ext sweep --scenario diamond --out sweep.csv` is run
- **THEN** it exits 0, and `sweep.csv` has 8 data rows (2 policies × 4 links) in the stated order

#### Scenario: Repeat run
- **WHEN** the same sweep command is run twice
- **THEN** the two CSV files are byte-identical

#### Scenario: Unknown policy
- **WHEN** the sweep is given a policy name that is not registered
- **THEN** it exits non-zero and names the policy
