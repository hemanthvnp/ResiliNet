## 1. Branch and hand-worked numbers (A, by H4)

- [ ] 1.1 Create the branch `feat/add-decision-explanations` from an up-to-date `main`
- [ ] 1.2 A works by hand the bound, gap and cut for the BD-failed diamond, the `max_paths` 1 diamond and the blocking example, and commits them as `core/explain/tests/expected_records.json`. An agent does not produce these values

## 2. Record builder (A, H4 to H8)

- [ ] 2.1 Add the builder interface in `core/explain/records.py` (facts in, `DecisionRecord` out) with baseline records, with tests: one record per flow, unique ids, empty `attempts` and `cut`, bound fields unset
- [ ] 2.2 Add the reference path and its status strings (`USED`, `PARTIAL`, `INVALID`, `NONE`), with a test for each status
- [ ] 2.3 Copy `previous` paths and `failed_links` into the record, with the L7 test from the section 10 fixture
- [ ] 2.4 Record attempts, with tests: two attempts for F1 on the healthy diamond, pushed amounts sum to delivered

## 3. Max-flow bound (A, H4 to H8)

- [ ] 3.1 Add `bound.py` (residuals with the flow's own reservations added back, then `min(rate, maxflow)`) and `greedy_gap`, with tests from `expected_records.json`: bound 10 and gap 0, bound 15 and gap 5, gap above 0 on the blocking example
- [ ] 3.2 Set bound and gap to 0 for `DISCONNECTED`, with a test

## 4. Residual cut (A, H8 to H12)

- [ ] 4.1 Add `cut.py` (arcs leaving the residual-reachable set, state `saturated` or `down`, sorted by arc id), with the BD-failed diamond test from `expected_records.json`
- [ ] 4.2 Attach `load_by_class` from `Ledger.class_breakdown`, with tests: class 0 holds 10 on the saturated arc; cut is empty under `PATH_LIMIT`, `DISCONNECTED` and `NONE`

## 5. Explanation template (A, H8 to H12)

- [ ] 5.1 Add `template.py` with the header, reference and attempt segments, printing paths as node sequences, with a test of the first two sentences of the section 10 line
- [ ] 5.2 Add the unserved segment, branching on `greedy_gap`, with tests: the full section 10 line matches exactly, and the heuristic wording
- [ ] 5.3 Add the `OVERLOAD_LOSS` and `DISCONNECTED` segments, with tests for each and for identical output on repeat
- [ ] 5.4 Add a test that the builder reproduces the section 10 fixture record exactly; a mismatch is raised with all four members, and the fixture is not edited to fit

## 6. Lazy mode (A, only if the A3 cut line triggers)

- [ ] 6.1 Add a flag to skip the bound at route time and a replay-up-to-flow function, with a test that the lazy value equals the eager value on every fixture

## 7. Integrate

- [ ] 7.1 Run the full test suite with `pytest`, and `check_invariants` (including I11) on every fixture snapshot
- [ ] 7.2 Rebase onto `main`
- [ ] 7.3 Run `sh .github/scripts/check-history.sh`
- [ ] 7.4 Open the pull request from `.github/pull_request_template.md`
