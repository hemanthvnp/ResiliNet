## 1. Branch and scaffold (C, H0 to H1.5)

- [x] 1.1 Create the branch `feat/add-frontend-ui` from an up-to-date `main`
- [x] 1.2 Add the Vite + React + TypeScript project in `frontend/` with Cytoscape.js, Recharts and a test runner, with one render test so the frontend build and tests pass
- [x] 1.3 Add the script that generates the typed client from the committed OpenAPI file, with a check that the generated types compile
- [x] 1.4 Add the graph component rendering a topology from a fixture with a fixed-seed layout, with a test that the same topology gives the same node positions
- [x] 1.5 Fetch a mocked snapshot from the API and render it (H1.5 exit criterion), with a test against a mocked response

## 2. Vertical slice (C, H1.5 to H4)

- [x] 2.1 Add the store (scenario, topology, flows, event history, per-panel run id and snapshot, shared selection), with reducer tests for each action
- [x] 2.2 Colour edges from `metrics.link_util` (sequential scale, overload colour above 1.0, dashed red for `down`, thickness by capacity), with tests: 0.2 and 0.95 map to the two ends, 2.5 gets the overload colour, a down link is dashed whatever its utilization
- [x] 2.3 Add click-to-fail and click-to-recover with a loading state and a click lock while in flight, with tests: an up link sends `fail`, a down link sends `recover`, a click during a request is ignored
- [x] 2.4 Add the flow table (class colour, service, demand, delivered, status) sorted by class then id, with a test of an unserved row
- [x] 2.5 Show request errors while keeping the last good snapshot, with a test of a failed event request
- [ ] 2.6 M1 check at H4 with the team: click a link and see both baselines reroute with metrics

## 3. Comparison view (C, H4 to H8)

- [x] 3.1 Create two runs per scenario, send each event to both and commit both snapshots together, with tests: both panels show the same step, a step mismatch shows the error banner
- [x] 3.2 Render two panels from the one graph component with shared positions and synchronised pan and zoom, with a test that both panels receive the same positions
- [x] 3.3 Add the baseline selector (S0-QoS default, S0) with history replay on switch, with tests: default is S0-QoS, switching after two events lands on the same step
- [x] 3.4 Add the KPI strip per panel (DR, DR_P0, DR_P1, overloaded links, unserved by cause, in a fixed order), with a test that each strip shows its own snapshot's values
- [x] 3.5 If behind at H8: ship stacked panels or a policy toggle with the same graph component

## 4. Inspection and generation (C, H8 to H12)

- [x] 4.1 Highlight the selected flow's routes on both graphs in the class colour, with a test that a two-path flow highlights both paths
- [x] 4.2 Add the decision panel (explanation line, attempts, cause, cut, max-flow bound, greedy gap), with tests: the section 10 fixture shows its explanation text unchanged, a `DISCONNECTED` flow is shown as physically disconnected
- [x] 4.3 Add the scenario selector, seed display and reset button, with tests: the seed is visible, reset returns both panels to step 0
- [ ] 4.4 Add the generate-network form (buildings, redundancy, seed) showing the effective seed, with a test that it posts a generator scenario and loads both panels
- [ ] 4.5 If behind at H12: show the decision record as formatted text; ship a seed field only
- [ ] 4.6 M3 check at H12 with the team: the demo scenario runs baseline and S2 with an explanation, and a generated network loads

## 5. Charts and polish (C, H12 to H16)

- [ ] 5.1 Add the benchmark chart (DR against load factor for S0-QoS and S2, from the benchmark CSV), with a test on a small CSV
- [x] 5.2 Add loading a saved run file with no server, with a test that both panels render the saved snapshots
- [ ] 5.3 Add the utilization legend and text labels, and check contrast and non-colour cues on the projector
- [x] 5.4 Add the demo-mode layout (large KPIs, hidden secondary labels)

## 6. Rehearsal (C, H16 to H22)

- [ ] 6.1 Set up and test on the demo laptop with the fallback run file ready
- [ ] 6.2 Perform the section 15 demo script twice, timed

## 7. Integrate

- [ ] 7.1 Run the frontend build and tests, and the full backend suite with `pytest`, which runs `check_invariants` on the snapshots the UI consumes
- [ ] 7.2 Rebase onto `main`
- [ ] 7.3 Run `sh .github/scripts/check-history.sh`
- [ ] 7.4 Open the pull request from `.github/pull_request_template.md`
