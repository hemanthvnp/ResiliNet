## 1. Branch

- [ ] 1.1 Create the branch `feat/submission-readiness` from an up-to-date `main`; verify with `git log -1 main` that it matches `origin/main`

## 2. README sections (D, can start at any time)

- [ ] 2.1 Write the README sections for team name and members, problem statement (Problem Statement 4) and technologies; verify that they render in the README
- [ ] 2.2 Write "External resources" with each library's license (networkx BSD-3-Clause, pydantic MIT, FastAPI MIT, pytest MIT, hypothesis MPL-2.0, scipy BSD-3-Clause, React MIT, Vite MIT, Cytoscape.js MIT, Recharts MIT), checked against each project's LICENSE file; verify that every dependency in the lockfiles is listed
- [ ] 2.3 Collect each member's AI tools and what they were used for, and write "AI tools used"; verify that all four members have a line
- [ ] 2.4 Start a "Challenges" list, one line per problem met during the hackathon, added as it happens; verify that it has entries before the H20 rehearsal

## 3. Judge kit (after B's template tuning at H10)

- [ ] 3.1 Add `examples/custom-flow.json`, `examples/custom-failure.json` and `examples/overload.json`, with a test that loads each one; verify the files-validate scenario
- [ ] 3.2 Add the test that runs every example under S0, S0-QoS, S1 and S2 with `check_invariants`; verify the all-examples scenario (12 runs) passes
- [ ] 3.3 Add the edited-priority and mistyped-link tests; verify that both pass
- [ ] 3.4 Write the "Try your own input" README section: one command per example and which fields to edit; verify that every documented command runs as written

## 4. Integrate

- [ ] 4.1 Run the full suite with `pytest`; verify that it passes
- [ ] 4.2 Rebase onto `main`, run `sh .github/scripts/check-history.sh`, and open the pull request from `.github/pull_request_template.md`
