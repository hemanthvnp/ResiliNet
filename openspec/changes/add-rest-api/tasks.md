## 1. Branch, skeleton and mocks (D, H0 to H1.5)

- [x] 1.1 Create the branch `feat/add-rest-api` from an up-to-date `main`
- [x] 1.2 Add `api/` with a FastAPI app, the uvicorn start command, local CORS and pinned dependencies, with an httpx test client and one test that the app starts
- [x] 1.3 Add request and response schemas in `api/schemas.py` from the shared models and declare all six routes with their status codes, with a test that each route is registered
- [x] 1.4 Add mock mode serving the snapshot fixtures, with tests that each mocked response validates against its schema
- [ ] 1.5 Export the OpenAPI schema to a committed file, with the schema-is-current test; all four members confirm it as part of the H1.5 freeze
  - Note (D): the schema is committed and tested (#19), and the frontend's types are generated from it (#22). A and B have since handed off, so the four-member confirmation was never formally recorded; C and D now own the contract.
- [x] 1.6 Confirm with C that the frontend renders a mocked snapshot fetched from the API (H1.5 exit criterion) and note it in the pull request description

## 2. Sessions and live baselines (D, H1.5 to H4)

- [x] 2.1 Add the session store (run ids, per-session lock, eviction by creation counter), with tests: two runs are isolated, the oldest run is evicted at the cap
- [x] 2.2 Add `GET /scenarios` from the scenario fixtures, sorted by id, with a test of the listing
- [x] 2.3 Add live `POST /runs` for a scenario id and for an inline scenario, returning topology, flows and the step-0 snapshot, wired to `S0` and `S0-QoS`, with tests: diamond run at step 0, unknown policy gives 422, unknown scenario gives 404
- [x] 2.4 Add `POST /runs/{id}/events` and `POST /runs/{id}/reset`, with tests: fail a link, unknown run gives 404, unknown link gives 422 and leaves the run unchanged, reset equals step 0
- [x] 2.5 Map core errors to 404 and 422 in one place, with a test per error type
- [ ] 2.6 M1 check at H4 with the team: a click in the UI reroutes both baselines and updates the metrics
  - Assigned to C with the other manual testing. C's session checked M1 at the API level (two runs on `02_uplink_failure`, L6 failed: S0-QoS DR 0.706 with 1 overloaded link, S2 DR 1.0 with none); the browser click-through remains.

## 3. Compare, decisions and generators (D, H4 to H12)

- [x] 3.1 Add `POST /compare` with a deep copy per policy and the headline table, with tests on the diamond: one row per policy, S2 has 0 overloaded arcs, same links and flows for every policy
- [x] 3.2 Add the decision endpoint (lazy bound if that mode is on), with tests: a record for an unserved S2 flow, unknown flow gives 404
- [x] 3.3 Accept generator specs in `POST /runs`, return the effective seed and map retry exhaustion to 422, with tests: the same request returns the same topology twice
- [x] 3.4 Wire `S1` and `S2` once the allocator lands, with a test that all four policy names create a run
- [x] 3.5 Measure the payload size and response time at 50 nodes and 200 flows and record them in the pull request description; dropping `decisions` from snapshots is a contract change that needs all four members

## 4. Hardening (D, H12 to H20)

- [x] 4.1 Add a test that no module under `core/` imports `fastapi` or `api`
- [x] 4.2 Add tests through the API for idempotent events, node failure and an empty link list; fix any failure in `api/`, or report it to the owner if it is in `core/`

## 5. Integrate

- [x] 5.1 Run the full test suite with `pytest`, and `check_invariants` on every snapshot the API tests receive in live mode
- [x] 5.2 Rebase onto `main`
- [x] 5.3 Run `sh .github/scripts/check-history.sh`
- [x] 5.4 Open the pull request from `.github/pull_request_template.md`
