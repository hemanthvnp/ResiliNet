## 1. Branch and hand-worked numbers (B, by H1.5)

- [ ] 1.1 Create the branch `feat/add-metrics-invariants` from an up-to-date `main`
- [ ] 1.2 B computes by hand every metric for the diamond under S0, S0-QoS and S2, both rows (section 4 table and section 8 formulas), and commits them as `core/metrics/tests/expected_diamond.json`. An agent does not produce these values
- [ ] 1.3 B computes by hand one case each for latency stretch, recovery ratio, churn and `dr_reach`, and commits them as `core/metrics/tests/expected_cases.json`

## 2. Basic metrics (B, H1.5 to H4)

- [ ] 2.1 Add `compute_metrics` with `dr`, `dr_by_class` and `unserved_by_cause`, summing in flow-id order, with tests from `expected_diamond.json`
- [ ] 2.2 Add `overloaded_arcs` and `overload_excess`, with tests: 2 arcs and excess 30 for S0 on the healthy diamond, 0 for S2
- [ ] 2.3 Add arc utilization and `link_util` (max of the two arcs), with tests: 0.8 and 0.2 give 0.8, offered load 25 on capacity 10 gives 2.5

## 3. Full metrics (B, H4 to H8)

- [ ] 3.1 Add `dr_reach`, `max_util`, `mean_util` and `arcs_above_90`, with tests from `expected_cases.json`
- [ ] 3.2 Add `latency_stretch` with healthy shortest-path latencies passed in, with tests: 1.0 on shortest paths, 2.0 on the detour case
- [ ] 3.3 Add `recovery_ratio` (unset when undefined), with tests: 15 after 20 gives 0.75, no affected flows gives unset
- [ ] 3.4 Add `churn_flows` and `churn_rate`, with the one-flow-moved test
- [ ] 3.5 Add `p0_greedy_gap` from decision records, pass `compute_ms` through, and add weighted delivery as a secondary helper, with a test for each
- [ ] 3.6 Handle empty cases (no flows, zero demand, nothing delivered), with a test that `dr` is 1.0 and nothing raises

## 4. Invariant checker (B, H4 to H8)

- [ ] 4.1 Add the violation type, `check_invariants` returning a sorted list, and a raising wrapper, with a test that the valid diamond fixtures report nothing
- [ ] 4.2 Add I1 and I2 (path validity), with one deliberately broken snapshot per invariant
- [ ] 4.3 Add I3 (demand accounting, tolerance 1e-9), with tests: 2.8 plus 4.2 of 7 passes, 11 of 10 is reported
- [ ] 4.4 Add I4 (capacity, S1 and S2 only) and I6 (arc load consistency), with tests: load 11 on capacity 10 is reported under S2 and not under S0
- [ ] 4.5 Add I7 with an independent connectivity query, with tests: false disconnection, missing cause
- [ ] 4.6 Add I9 (recompute metrics and compare), with a tampered-`dr` test
- [ ] 4.7 Add the I8 comparison helper and the I10 class-isolation helper, with a test for each; add the I5 ledger test

## 5. I11 (B, H8 to H12)

- [ ] 5.1 Add I11 once decision records carry the cut and the bound, with tests: a cut under `PATH_LIMIT` and a negative gap are reported

## 6. Integrate

- [ ] 6.1 Run the full test suite with `pytest`, and `check_invariants` on every fixture snapshot under all four policies
- [ ] 6.2 Rebase onto `main`
- [ ] 6.3 Run `sh .github/scripts/check-history.sh`
- [ ] 6.4 Open the pull request from `.github/pull_request_template.md`
