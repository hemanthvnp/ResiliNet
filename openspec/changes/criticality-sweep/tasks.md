## 1. Branch, review and tests first

- [ ] 1.1 Create the branch `feat/criticality-sweep` from an up-to-date `main`; verify with `git log -1 main` that it matches `origin/main`
- [ ] 1.2 A human re-works by hand the diamond and two-node numbers in `specs/criticality-sweep/spec.md` and records "checked by <name>" in the PR description; verify every scenario value matches
- [ ] 1.3 Send the spec and design to ChatGPT for an adversarial review (PLAN-CYCLE2.md §8); record each finding and its resolution in the PR, and update the spec and design first if any is accepted
- [ ] 1.4 ChatGPT writes `ext/tests/test_sweep.py` from the spec scenarios only; verify that the tests fail because `ext/sweep.py` does not exist yet. Tasks 1.1 to 1.4 can run before H16.

## 2. Sweep

- [ ] 2.1 Implement the per-link fail, read and reset loop over one `Simulation` per policy in `ext/sweep.py`; verify that the diamond S2 and S0-QoS scenarios and the reset-equality scenario pass
- [ ] 2.2 Add bridge detection on the healthy topology, the structural and operational groups, the drop columns and the shared-tie ranking; verify that the two-node structural scenario, the all-operational diamond scenario and the shared-rank scenario pass

## 3. Command and output

- [ ] 3.1 Add the `sweep` subcommand to `ext/__main__.py` with the CSV writer and the structural and top-5 operational printout; verify the default-run, repeat-run (byte-identical) and unknown-policy scenarios
- [ ] 3.2 Run the sweep on the campus template, record the structural list and the top-5 operational table in the PR description, and add a "Single-link sensitivity" paragraph using the PLAN-CYCLE2.md §4 wording to the README; verify that the documented command runs as written

## 4. Integrate

- [ ] 4.1 Send the diff to Gemini or ChatGPT for an adversarial review; fix accepted findings in the branch and record them in the PR
- [ ] 4.2 Run the full suite with `pytest`, and `check_invariants` on every snapshot the sweep produces on the campus template; verify that all pass
- [ ] 4.3 Rebase onto `main`, run `sh .github/scripts/check-history.sh`, and open the pull request from `.github/pull_request_template.md`
