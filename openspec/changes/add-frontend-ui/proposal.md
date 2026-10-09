## Why

The demo is two to three minutes in front of judges, and the argument is visual: the same network, the same failure, a QoS baseline on the left and S2 on the right. PLAN.md section 10 lists seven things the UI must do for a convincing demo, including generating a network on screen, which is how the problem statement's "create or generate a network topology" is met.

## What Changes

- Add a React + Vite + TypeScript app with a typed client generated from the OpenAPI schema.
- Add the topology graph (Cytoscape.js): link colour from `metrics.link_util`, overload colour above 1.0, failed links red dashed, thickness by capacity, labels for key services.
- Add click-to-fail and click-to-recover on links.
- Add the side-by-side view: the same network under a baseline and S2, the same event applied to both, with a baseline selector (S0-QoS default, or S0).
- Add a KPI strip per side: DR, DR_P0, DR_P1, overloaded links, unserved by cause.
- Add the flow table with class colour, demand, delivered and status; selecting a flow highlights its routes and opens its decision record with the one-line explanation.
- Add the scenario selector, seed display and reset button.
- Add the generate-network form (buildings, redundancy, seed).
- Optional: benchmark charts (Recharts) from the benchmark CSV, loading a saved fallback run, demo-mode layout.

## Non-goals

- Any routing, metric or utilization computation in the browser (PLAN.md section 7, link display rule).
- WebSocket push, hover what-if preview, natural-language box, timeline scrubber (PLAN.md sections 1, 10 and 14).
- Mobile layout; the target is the demo laptop and a projector.

## Capabilities

### New Capabilities
- `web-ui`: the interactive network view, side-by-side policy comparison, KPIs, flow inspection, scenario and generator controls.

### Modified Capabilities

None.

## Impact

- **Owner:** C.
- **Folders:** `frontend/` only (including its tests).
- **PLAN.md sections implemented:** 6 (React, Vite, TypeScript, Cytoscape.js, Recharts), 7 (link display rule), 10 (minimum UI items 1 to 7, optional polish), 11 (C's row), 12 (C's column and the frontend cut lines), 15 (demo script).
- **Frozen contract:** not touched. The typed client is generated from the committed OpenAPI file and the fixtures are read as mock data; neither is edited. A shape the UI needs and the contract lacks is raised with all four members.
- **Dependencies:** React, Vite, TypeScript, Cytoscape.js, Recharts, an OpenAPI client generator.
- **Depends on:** `add-rest-api` (mocks from H1.5, live from H4).
- **Window:** scaffold H0 to H1.5; vertical slice H1.5 to H4; comparison view H4 to H8; inspection and generation H8 to H12; charts and polish H12 to H16.
