## Context

PLAN.md section 6 picks React, Vite, TypeScript, Cytoscape.js and Recharts, with REST only. Section 10 lists the minimum UI and section 12 gives cut lines for the side-by-side view, the flow inspector and the generate form. The backend computes everything; the UI renders snapshots.

## Goals / Non-Goals

**Goals:**
- The demo script in section 15 can be performed end to end with clicks only.
- The UI works against mocks and live data with no code change.
- Both panels are visibly the same network in the same layout.

**Non-Goals:**
- Any routing, metric or utilization computation in the browser.
- WebSocket push, hover what-if preview, natural-language box, timeline scrubber.
- Mobile layout. The target is the demo laptop and a projector.

## Decisions

**The UI never derives values.** Link colour comes from `metrics.link_util`, KPIs from `metrics`, statuses from `FlowResult.cause`, explanation text from `DecisionRecord.explanation`.
*Rejected:* computing utilization from `arc_load` in the client, because the link display rule in section 7 forbids it and two implementations of one formula can disagree on stage.

**Side-by-side is two runs of the same scenario.** The app creates one run per panel and sends every event to both in parallel, then renders both snapshots together. Changing the baseline selector creates a new run for the left panel and replays the event history to it.
*Rejected:* calling `POST /compare` on every click, because it reruns the whole history each time.

**One graph component, used twice, with one layout.** Both panels get the same node positions from a layout computed once per topology; pan and zoom are synchronised.
*Rejected:* letting each panel lay itself out, because different node positions would hide the one difference the demo is about.

**State lives in one reducer with React context.** It holds the scenario, topology, flows, the event history, and per panel the run id and current snapshot. Selection is shared, so a selected flow is highlighted in both panels.
*Rejected:* a state library, because the state is small and a new dependency buys nothing in 24 hours.

**Colour carries three meanings, kept apart.** Link colour is a sequential green-to-red scale for utilization 0 to 1 with a distinct overload colour above 1.0. Failed links are dashed and drawn from `link_state`. Flow class has its own three-colour categorical set, used only in the flow table and route highlights. Each meaning also has a non-colour cue (dash pattern, text label, thickness).
*Rejected:* one scale that also encodes failure, because a failed link and an overloaded link would both read as "red" on a projector.

**The typed client is generated from the committed OpenAPI file** by a script and never edited by hand.
*Rejected:* hand-written types, because contract drift would then surface on stage and not at compile time.

**Requests are serialised.** A click is ignored while an event is in flight, and both panels update together when both responses arrive.
*Rejected:* queueing clicks, because a queued click was aimed at a picture that is already out of date.

**A saved run can be loaded from a file.** The app replays the `/compare` output with no server.
*Rejected:* relying on the recorded video alone, because a video cannot answer a judge who asks to fail a different link.

**Cut lines are designed in.** Side-by-side falls back to two stacked panels or a policy toggle using the same graph component; the flow inspector falls back to the decision record as formatted text; the generate form falls back to a seed field.
*Rejected:* building the fallbacks only when needed, because at H8 or H12 there is no time to restructure components.

**Determinism.** The layout uses a fixed seed and is computed once per topology, so the same network always appears in the same place and both panels match. The flow table is sorted by class then flow id, KPI causes appear in a fixed order, and event history is replayed in order. The UI generates no random values of its own; the seed field is sent to the backend as typed.
*Rejected:* a force layout with a random start, because the demo network would look different at every rehearsal.

## Risks / Trade-offs

- [Contract drift] → Generated types and mocks from H1.5.
- [The two panels get out of step] → Events are sent to both runs and committed to state together; a step mismatch shows an error banner instead of a silent wrong picture.
- [Cytoscape is slow with route highlights at 50 nodes] → Batch style updates; labels can be hidden.
- [Layout shifts between events] → Positions are fixed after the first layout.
- [Demo machine failure] → Fallback run file; C owns the demo laptop setup and tests on it at H20.
