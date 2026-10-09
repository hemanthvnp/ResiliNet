## 1. Branch, review and tests first

- [ ] 1.1 Create the branch `feat/ecmp-baseline` from an up-to-date `main`; verify with `git log -1 main` that it matches `origin/main`
- [ ] 1.2 A human re-works by hand the square and diamond numbers in `specs/ecmp-routing/spec.md` and records "checked by <name>" in the PR description; verify every scenario value matches the hand calculation
- [ ] 1.3 Send the spec and design to ChatGPT for an adversarial review (PLAN-CYCLE2.md §8); record each finding and its resolution in the PR description, and update the spec and design first if any is accepted
- [ ] 1.4 ChatGPT writes `ext/tests/test_ecmp.py` from the spec scenarios only, without seeing any implementation; verify that the tests fail with ImportError because `ext/ecmp.py` does not exist yet. Tasks 1.1 to 1.4 can run before H16, since they change no frozen file.

## 2. Example data

- [ ] 2.1 Add `examples/square.json`, `examples/shared-prefix.json` and `examples/eight-paths.json` as defined in the spec scenarios, with a test that each validates as a `Scenario`; verify with `pytest ext/tests -k examples_load`

## 3. Policy

- [ ] 3.1 Implement the next-hop walk and the integer split per next hop in `ext/ecmp.py`; verify that the square, shared-first-hop and eight-next-hop scenarios in `test_ecmp.py` pass
- [ ] 3.2 Implement `ECMP` and `ECMP-QoS` delivery, reusing A's delivery functions if they are exposed and repeating the formulas otherwise; verify the square and diamond delivery scenarios pass
- [ ] 3.3 Register both names in `ext/__init__.py` and add `ext/__main__.py`, which hands `run` and `compare` to the cycle-1 CLI; verify that `python -m ext compare --scenario examples/square.json --policies S0-QoS ECMP-QoS S2` prints DR 0.40, 0.80 and 0.80
- [ ] 3.4 Add a hypothesis test that runs `ECMP` and `ECMP-QoS` on random seeded campus scenarios with `check_invariants` (I4 excluded) and a repeat-run equality check; verify that it passes and prints the seed on failure
- [ ] 3.5 Add the eight-route regression test: ECMP-QoS 80, S0-QoS 10, S2 30 at `max_paths` 3 with cause `PATH_LIMIT` and greedy gap 50, and S2 80 at `max_paths` 8; verify that it passes

## 4. Docs

- [ ] 4.1 Add an "ECMP-style baseline" paragraph to the README. It covers the idealised next-hop split, the fact that routers hash flows, the square and eight-route results, and why S2 is also reported at `max_paths` 8. Use the PLAN-CYCLE2.md §4 wording; verify that the documented commands run as written

## 5. Integrate

- [ ] 5.1 Send the diff to Gemini or ChatGPT for an adversarial review; fix accepted findings in the branch and record them in the PR
- [ ] 5.2 Run the full suite with `pytest`, and `check_invariants` on every ECMP snapshot of `examples/square.json` and the campus template; verify that all pass
- [ ] 5.3 Rebase onto `main`, run `sh .github/scripts/check-history.sh`, and open the pull request from `.github/pull_request_template.md`
