## 1. Branch and hand-worked numbers (A, H0 to H1.5)

- [x] 1.1 Create the branch `feat/add-routing-policies` from an up-to-date `main`
- [x] 1.2 A works the diamond by hand for S0, S0-QoS and S2, both rows, checks it against the section 4 table, and commits the numbers as `core/routing/tests/expected_diamond.json`. An agent does not produce these values
- [x] 1.3 A works by hand one blocking example (shortest-path pushes deliver less than max-flow), one `PATH_LIMIT` case and one `util_cap` 0.9 case, and commits them as `core/routing/tests/expected_cases.json`

## 2. Pathfinder (A, H1.5 to H2.5)

- [x] 2.1 Add heap-based Dijkstra over sorted arcs with integer weights and tie-break `(cost, hops, node ids)`, with tests: lowest cost, fewer hops on a tie, node ids on a full tie, parallel links, down link avoided, no path
- [x] 2.2 Add connected components and residual reachability, with tests: isolated node, saturated arc blocks reachability
- [x] 2.3 Add max-flow value (networkx), with the diamond test (value 20), and a test that no policy module imports networkx

## 3. Baselines (A, H2.5 to H4)

- [x] 3.1 Add S0 routes and offered `arc_load`, flows sorted by id, with tests: both diamond flows on A-B-D with load 25, a disconnected flow
- [x] 3.2 Add the S0 single-pass delivery model and causes, with tests from `expected_diamond.json` (both rows) and the non-integer case (2.8 of 7)
- [x] 3.3 Add S0-QoS per-arc, per-class scale factors on the S0 routes, with tests from `expected_diamond.json`, routes equal to S0, and P0 and P1 unchanged when P2 is removed
- [x] 3.4 Add the policy registry with `S0` and `S0-QoS`, with tests: lookup by name, unknown name raises, repeat run gives an equal allocation

## 4. Allocator (A, H4 to H8)

- [x] 4.1 Add the ordering policies (`arrival`, `class_size_desc`, `class_size_asc`) with flow id as the last key, with tests: critical flow first, arrival ignores class
- [x] 4.2 Add the integer cost function with Fortz-Thorup slopes and integer threshold comparison, with tests: lambda 0 is pure latency, slope at each threshold
- [x] 4.3 Add the push loop on the residual graph with the ledger, `max_paths` and `util_cap`, with tests from `expected_diamond.json` (S2, both rows) and capacity never exceeded
- [x] 4.4 Add cause assignment (`DISCONNECTED` from components, `PATH_LIMIT`, `INSUFFICIENT_CAPACITY`), with tests from `expected_cases.json`
- [x] 4.5 Handle `src == dst` and zero-rate flows, with a test for each
- [x] 4.6 Collect per-flow facts and call the record builder in `core/explain/`, with a test that one record is returned per flow
- [x] 4.7 Register `S1` and `S2` as configurations of the allocator, with tests: S1 never splits, `prev` is ignored, class isolation when P2 is removed
- [x] 4.8 Run the H8 headline check with the team (S0, S0-QoS, S2 on the campus template, uplink failed) and record `DR`, `DR_P1`, `DR_P0` in the pull request description

## 5. Ablation and tuning (A, H8 to H16)

- [x] 5.1 Run the ablations on ordering, `max_paths`, `congestion_lambda`, `util_cap`, one knob at a time, and record the table in the pull request description
- [x] 5.2 Set the S2 defaults from the data; if the congestion cost shows no benefit, remove it with its tests and say so in `CHANGELOG.md`
- [x] 5.3 Time the recompute at 50 nodes and 200 flows; if it is 1 second or more, apply the A3 cut line (lazy bounds, then `max_paths = 2`)

## 6. Optional, only if core is stable at H12

- [x] 6.1 Add upstream-aware baseline delivery behind a flag (up to 50 rounds, tolerance 1e-9), with a hand-worked two-link test
- [x] 6.2 Add the LP reference with scipy HiGHS on 20 to 30 nodes, labelled "fractional upper bound", with a test that it is never below S2 on the diamond

## 7. Integrate

- [x] 7.1 Run the full test suite with `pytest`, and `check_invariants` on every fixture snapshot under all four policies (done: B's `check_invariants` found no violation in 272 snapshots of A's four policies on 35 networks, and `core/routing/tests/test_invariants_on_policies.py` keeps running it; issue 14)
- [x] 7.2 Rebase onto `main`
- [x] 7.3 Run `sh .github/scripts/check-history.sh`
- [x] 7.4 Open the pull request from `.github/pull_request_template.md` (PRs 2, 3, 4, 6, 7, 8, 10 and 13, merged one by one as the work became possible)
