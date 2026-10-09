## Why

The frontend needs a stable contract to code against from hour 1.5, before any routing exists, and the core library must stay free of web imports. PLAN.md section 7 fixes six REST endpoints; a thin FastAPI layer serves mocks first and the real policies from H4.

## What Changes

- Add a FastAPI app with the six endpoints of section 7: list scenarios, create a run, apply an event, reset a run, compare policies, fetch one flow's decision record.
- Add in-memory sessions: one `Simulation` per run id.
- Add **mock mode**: the same endpoints answer from the snapshot fixtures, so the frontend works from H1.5.
- Add the OpenAPI schema as part of the frozen contract, generated from the pydantic models.
- Add the scenario loader wiring for built-in scenarios, inline scenarios and generator specs (the UI's "Generate network" control).
- Add local-development CORS and a one-command start.

## Non-goals

- Authentication, persistence, multi-process deployment, WebSocket push (PLAN.md sections 2 and 6).
- Running the benchmark over HTTP; the CLI does that.
- Any routing, simulation or metric logic in `api/`.

## Capabilities

### New Capabilities
- `rest-api`: the HTTP endpoints, session handling, mock mode, error responses and the OpenAPI contract.

### Modified Capabilities

None.

## Impact

- **Owner:** D.
- **Folders:** `api/` and `tests/api/`.
- **PLAN.md sections implemented:** 6 (thin FastAPI, REST only, core purity rule), 7 (REST API table), 11 (D's row; OpenAPI in the shared contract), 12 (D's column and the H4 cut line).
- **Frozen contract:** touched. This change creates the OpenAPI schema file, which is frozen at H1.5 with `types.py` and the fixtures. After the freeze, a change to the schema needs all four members to agree, and the fixtures change first. Mock mode reads `fixtures/` and does not edit it.
- **Dependencies:** FastAPI, uvicorn, httpx (tests), with pinned versions.
- **Depends on:** `add-core-model-contract` at H1.5 for mocks; then `add-simulation-engine`, `add-routing-policies`, `add-network-generators`, `add-decision-explanations`.
- **Depended on by:** `add-frontend-ui`.
- **Window:** skeleton and mocks H0 to H1.5; sessions and live baselines H1.5 to H4; `/compare` H4 to H8.
