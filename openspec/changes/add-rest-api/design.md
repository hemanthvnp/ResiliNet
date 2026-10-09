## Context

PLAN.md section 6 chooses REST only: each event recompute is a request and a response, and WebSocket would add failure modes for no demo benefit. The API is thin and holds in-memory sessions. Section 7 lists the endpoints; request and response bodies beyond the listed fields are decided here.

## Goals / Non-Goals

**Goals:**
- C can build the whole UI against mocks from H1.5 and switch to live data without code changes.
- No routing, metric or simulation logic in `api/`.
- The OpenAPI schema is generated, never hand-written.

**Non-Goals:**
- Authentication, persistence, multi-process deployment, WebSocket push.
- Benchmark execution over HTTP (the CLI does that).

## Decisions

**Request and response shapes.**

| Endpoint | Request | Response |
|---|---|---|
| `GET /scenarios` | none | list of `{id, name, description}` |
| `POST /runs` | `{scenario_id` or `scenario, policy, config?}` | `{run_id, scenario, topology, flows, snapshot}` |
| `POST /runs/{id}/events` | `{kind, links?, node?}` | `Snapshot` |
| `POST /runs/{id}/reset` | none | `Snapshot` |
| `POST /compare` | `{scenario_id` or `scenario, policies[], config?}` | `{scenario, topology, flows, table, snapshots}` |
| `GET /runs/{id}/flows/{flow_id}/decision` | none | `DecisionRecord` |

`POST /runs` returns the resolved topology, flows and scenario alongside the step-0 snapshot. A snapshot holds link state and allocation but not capacities or flow demands, and the UI needs those to draw the graph and the flow table; the resolved scenario shows the effective seed after a generator retry.
*Rejected:* returning only the snapshot and adding a `GET /runs/{id}/topology` endpoint, because that is a seventh endpoint outside section 7 and a second round trip on every load.

**`/compare` runs each policy through the scenario's full event list** on deep copies and returns, per policy, the list of snapshots, plus a `table` of final-step headline metrics. The interactive side-by-side view holds two runs instead; `/compare` serves the scripted comparison and the fallback run JSON.
It also returns the resolved topology and flows, as `POST /runs` does, so a saved `compare --out` file renders offline (frontend task 5.2).
*Rejected:* returning only the final snapshot per policy, because the saved fallback run must show the progression.

**Sessions are a dict keyed by a server-generated run id.** The process is single-worker and local. Each simulation call is guarded by a per-session lock, and a session cap evicts the oldest run.
*Rejected:* stateless requests carrying the full event history, because every click would replay the whole history and section 6 specifies in-memory sessions.

**The step is assigned by the server.** The events endpoint takes `kind`, `links` and `node`; the session supplies the next step number.
*Rejected:* the client sending the step, because a double click or a second tab could send a stale one.

**Mock mode is a start-up switch on the same app.** With it on, `POST /runs` returns the step-0 fixture for the requested policy and the events endpoint returns the next recorded snapshot. Routes, models and status codes are identical in both modes.
*Rejected:* a separate mock server, because two servers can drift apart.

**Errors are 404 or 422.** Unknown run, scenario or flow id gives 404. An unknown policy, link or node id, a malformed body, or a generator that exhausts its retries gives 422 with a message naming the bad value. Core exceptions are mapped in one place.
*Rejected:* a single 400 for everything, because the frontend must tell a lost session (create a new run) from bad input (show the message).

**The decision endpoint returns the record of the current step.** If the bound is in lazy mode it is computed on this request by replay.
*Rejected:* a step parameter with stored history, because the UI only shows the current step and every past snapshot would have to be kept.

**OpenAPI is exported to a committed file at H1.5.** C generates a typed client from the file without the server running.
*Rejected:* the frontend reading `/openapi.json` from a running server, because the contract would then have no reviewable, diffable form to freeze.

**Determinism.** The run id is the only random value and it never appears inside a snapshot, so two runs of the same scenario return equal snapshots apart from `compute_ms`. Scenarios are listed sorted by id, the compare table is ordered as the request's `policies` list, and eviction follows a creation counter, not a clock. Mock responses are read from fixtures in a fixed step order.
*Rejected:* deriving the run id from the scenario and policy, because two panels opening the same scenario and policy would then share one session.

## Risks / Trade-offs

- [Contract drift between frontend and backend] → Schema generated from the frozen models; a test fails if the committed schema differs from the generated one.
- [Sessions lost on restart] → Accepted; reset and seeds make any state reproducible.
- [Large payloads at 200 flows with full decision records] → Measured at H8; if slow, snapshots omit `decisions` and the UI uses the decision endpoint. That is a contract change and needs all four members.
- [D is behind at H4] → Cut line: B pairs with D until M1 passes.
