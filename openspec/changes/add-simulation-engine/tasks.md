## 1. Branch and minimal simulation (B, H1.5 to H4)

- [ ] 1.1 Create the branch `feat/add-simulation-engine` from an up-to-date `main`
- [ ] 1.2 Add the scenario loader for JSON files and inline scenarios, resolving specs through `core/gen`, with tests: the diamond loads, a flow with an unknown node is rejected
- [ ] 1.3 Add `Simulation.__init__` with a step-0 route and snapshot, timing `policy.route` and passing `compute_ms` to metrics, with a test that step 0 validates as a `Snapshot`
- [ ] 1.4 Add `apply` for link `fail` and `recover` (atomic state change in sorted id order, full recompute, snapshot assembly), with tests: fail BD on the diamond, recover it, three links in one event give one snapshot

## 2. Full event semantics (B, H4 to H8)

- [ ] 2.1 Add node expansion for fail and recover events, with a test that a failed building switch disconnects its flows
- [ ] 2.2 Make events idempotent and reject unknown link and node ids before changing state, with tests: fail twice, unknown link leaves step and states unchanged
- [ ] 2.3 Add affected-flow detection before rerouting, with tests: flows on the failed link are listed, a recovery lists none
- [ ] 2.4 Add `reset`, with a test that it equals the original step-0 snapshot apart from `compute_ms`
- [ ] 2.5 Add the invariant-checking constructor flag, with a test that a violating snapshot raises with the invariant id
- [ ] 2.6 Add the scenario runner returning the snapshot sequence with a deep copy per policy, with tests: steps 0, 1, 2 for two events; S2 after S0 equals S2 alone

## 3. Determinism (B, H4 to H8)

- [ ] 3.1 Add snapshot serialization with sorted keys and `compute_ms` masked, with the I8 test that two runs are byte-identical
- [ ] 3.2 Add a test that the same scenario run in two fresh processes gives identical output
- [ ] 3.3 Add a test that three links failed in one event equal the same three failed in three events, apart from step and `compute_ms`

## 4. Scenario fixtures (B, H4 to H12)

- [ ] 4.1 Add the parametrised fixture test that runs each file under `fixtures/scenarios/` and checks its `expect` block, with fixture 7 (diamond; exact numbers for S0, S0-QoS, S2 written by B from the section 4 table)
- [ ] 4.2 B hand-works and adds fixtures 1 (normal) and 2 (single critical-link failure) on the campus template, after all four members agree
- [ ] 4.3 B hand-works and adds fixture 3 (three links, simultaneous and sequential), after all four members agree
- [ ] 4.4 B hand-works and adds fixture 4 (two alternates, one nearly full), after all four members agree
- [ ] 4.5 B hand-works and adds fixtures 5 (demand above min-cut) and 6 (isolated hostel), after all four members agree
- [ ] 4.6 B hand-works and adds fixture 8 (fail then recover) at H8 to H12, after all four members agree

## 5. Audit (B, H12 to H16)

- [ ] 5.1 Add tests for the section 13 edge cases through the simulation: two flows on the same pair, a capacity-0 link, parallel links, all P0 saturating a bottleneck; fix any failure in the code

## 6. Integrate

- [ ] 6.1 Run the full test suite with `pytest`, and `check_invariants` on every snapshot of all eight fixtures under all four policies
- [ ] 6.2 Rebase onto `main`
- [ ] 6.3 Run `sh .github/scripts/check-history.sh`
- [ ] 6.4 Open the pull request from `.github/pull_request_template.md`
