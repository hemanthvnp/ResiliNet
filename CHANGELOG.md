# Changelog

Notable changes to this project, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Benchmark results (`results/`): the 30-seed run on commit `f45c9c0` (3960
  rows, no matrix reduction, 88 s), the summary, the tables and the hypothesis
  verdicts. H1 passed: S2 delivers 14.0 points more than S0-QoS under stress, 95%
  CI 13.1 to 15.1. H1b passed: P0 delivery is a tie. H2 failed in S2's favour:
  +2.1 points when uncongested. H3 passed: S2 never overloaded an arc in 1800
  runs. H4 passed: median recompute 51 ms. H5 passed: zero P0 greedy gap in all
  720 runs. The README Results and Limitations sections report them.
- Judge kit (`examples/`): editable scenarios `custom-flow.json` (an added P0 flow
  from Admin to Engineering), `custom-failure.json` (L6, L11 and L13 fail, then L6
  recovers) and `overload.json` (40 generated flows at load factor 1.5). Each
  runs with `python -m cli run --scenario examples/<file>.json --policy S2` under
  all four policies with every invariant checked. Edited classes and ids take
  effect on the next run, and a mistyped id is rejected by name.
- README sections for submission: scope (a simulation of the controller, with an
  SDN island as the deployment path), a licence for every direct dependency read
  from its own LICENSE file, AI use for every member, a challenges list, and
  "Try your own input" for the judge kit.

- `README.md`: problem and solution, how to run the backend, frontend, command
  line and tests (checked on a fresh clone), demo steps, reproducing a run from a
  seed, the model, the allocator pseudocode, the diamond worked example, an
  architecture diagram, how correctness is checked, the results measured so far,
  limitations, technical contribution, future work, external resources and the AI
  use disclosure, the team (Claude Maxxers) and the official problem statement.
  The 30-seed benchmark results are still to be added.
- Single-link sensitivity sweep (`python -m ext sweep --scenario <file|id>`,
  `ext/sweep.py`): fails each link alone from the healthy state, per policy (S2
  and S0-QoS by default), and reports post-failure DR_P0, DR, overloaded arcs and
  the drop from the healthy values side by side. Bridges are listed as a
  structural group with the demand they cut off; the rest are ranked, with exact
  ties sharing a rank. The CSV is byte-identical between runs. On the campus
  template, S2 keeps every P0 flow for every single non-bridge failure, while the
  primary uplink L6 is S0-QoS's worst (DR 0.706, one overloaded link). `ext/` is
  added to the package list.

- Command line (`python -m cli`): `run --scenario <file|id> --policy <name>` writes
  the snapshot sequence as JSON, and `compare --scenario <file|id> [--policies ...]`
  prints the headline metrics per step and policy. `compare --out` writes the same
  body as `POST /compare`, which the frontend plays back offline. Policy knobs are
  flags: `--order`, `--max-paths`, `--lambda` and `--util-cap`. It never imports
  the API, so it works with no server running.
- Property tests (`tests/property/`): hypothesis draws campus networks, traffic
  and fail or recover events through the generators, then runs every invariant
  (I1 to I4 and I6 to I11) on every snapshot under all four policies. The run is
  derandomized, so CI and laptops draw the same 25 cases. A failure ends with a
  `check_case(...)` line that replays it.

- Simulation engine (`core/sim/`): `Simulation` builds step 0 from a scenario and
  a policy, applies fail and recover events (links or a node) atomically with a
  full recompute, lists affected flows, times the route call and can check every
  snapshot's invariants; `reset`, `from_inputs`, `run_scenario` and `serialize`
  (I8 form, `compute_ms` masked). The eight PLAN.md section 9 scenarios are
  fixtures under `fixtures/scenarios/`, each with its hand-worked `expect` block,
  plus the `congestion` and `line` topologies (agreed by all four members).
  Simultaneous and sequential failures give the same state; the event measures
  (`affected_flows`, recovery ratio, churn) describe each event and differ.
- Frontend comparison UI (`frontend/`) wired to the REST API: two synced panels
  (baseline and S2) with KPI strips, flow table, route highlight, decision panel,
  scenario selector, labelled link states with one legend, a MOCK DATA badge in
  mock mode, a demo mode (`?demo=1`) and playback of a saved `compare` file with
  no server. Contract types are generated from `api/openapi.json`
  (`npm run generate-client`).
- Metrics and the invariant checker (`core/metrics/`): `compute_metrics` gives every
  PLAN.md section 8 measure from the topology, flows and allocation alone, and
  `check_invariants` reports every violation of I1 to I11 at once, sorted, sharing
  no code with the policies. Helpers for I8 (`snapshots_identical`) and I10
  (`class_isolation`).
- Routing policies and decision records (`core/routing/`, `core/explain/`): S0
  (latency shortest path, proportional loss), S0-QoS (the same routes with strict
  priority on each arc), S1 and S2 (one allocator: flows placed in order on the
  residual graph by repeated least-cost pushes, split over at most `max_paths`
  paths) as `RoutingPolicy` objects selected with `get_policy(name)`. One
  `DecisionRecord` per flow: reference path and status, each push, the residual
  cut, the max-flow bound and the greedy gap, and a one-line explanation from a
  fixed template. All four policies reproduce the frozen diamond snapshots and the
  builder reproduces the section 10 record. Optional: upstream-aware baseline
  delivery (`upstream_aware=True` on `route_s0` and `route_s0_qos`) and an LP
  reference (`core/routing/lp_reference.py`, needs scipy). Measured on the campus
  generator at 50 nodes and 200 flows: S2 recompute 126 to 377 ms (worst 458 ms),
  P0 greedy gap zero on 180 of 180 runs. Behaviours a caller must know:
  - `route` takes an optional `step=` keyword; without it every record says step 0.
  - A record's `failed_links` are the down links that flow's previous paths
    crossed, so `prev` must be passed for a record to show `INVALID: <link> down`.
  - Duplicate flow ids, negative rates, `max_paths` below 1, a negative
    `congestion_lambda` and a `util_cap` outside (0, 1] raise `ValueError`.
  - Class isolation (I10) holds only under a class-first `order`.
  - `check_invariants` (I1 to I4, I6 to I9, I11) and the I10 helper report nothing
    for the four policies on the diamond fixtures, the campus template and 30
    generated networks, healthy and with the uplink failed (272 snapshots);
    `core/routing/tests/test_invariants_on_policies.py` keeps running it.
- Campus network for the demo and the benchmark (`core/gen/`): the hand-drawn
  campus template (15 nodes, primary uplink L6, two single-link hostels) and its
  traffic (19 flows, load factor 0.5) as fixtures; a seeded campus generator
  (default 50 nodes) and a seeded traffic generator (default 200 flows); load-factor
  scaling; and the PLAN.md section 9 post-failure path check. `resolve_inputs`
  retries a generated network up to 20 seeds and reports the seed it used; space
  benchmark seeds at least 20 apart. H8 headline check: with L6 failed, S2 delivers
  DR 1.000 and DR_P1 1.000 against S0-QoS 0.706 and 0.750.
- Shared contract frozen (H1.5, agreed by A, B, C and D): every PLAN.md section 7
  model in `core/model/types.py`, the arc model, the capacity `Ledger`, and the
  validating fixtures under `fixtures/` (the diamond under S0, S0-QoS, S1 and S2,
  an S0 snapshot with fractional delivery, the section 10 decision record).
  From now on, changing `types.py` or `fixtures/` needs all four members to agree,
  and the fixtures change first.
  - `Ledger.reserve` and `release` take the flow's class: `(path, rate, cls)`,
    not the `(path, rate)` of PLAN.md section 7, so `class_breakdown` can
    attribute a cut.
  - Snapshot conventions fixed by the fixtures: `arc_load` lists every available
    arc, zeros included; `dr_by_class` lists only classes that have flows;
    `unserved_by_cause` lists only causes with unserved traffic; `arcs_above_90`
    counts utilization above 0.9; `mean_util` is over all available arcs;
    `compute_ms` is 0.0 in fixtures.
  - Changed (agreed by A, B, C and D): `diamond_healthy_s1.json` now carries the
    S1 decision records for F1 and F2, so its `p0_greedy_gap` of 5.0 can be
    recomputed from the snapshot (invariant I9). The other diamond snapshots keep
    empty `decisions`.
- `AGENTS.md` with the rules shared by every member's coding agent.
- S2 defaults confirmed by ablation on 30 campus networks: `class_size_desc`,
  `max_paths` 3, `congestion_lambda` 0, `util_cap` 1.0. The congestion cost
  (`congestion_lambda` above 0) lowered delivery by 0.2 to 3.3 points and raised
  latency stretch by 7 to 30%, so it is not used; it stays in the code with the
  default 0 because the field is part of the frozen contract. See
  `core/routing/tests/ablation.py` and PR 13.
- REST API skeleton (`api/`): the six PLAN.md section 7 routes, request and
  response envelopes in `api/schemas.py`, local CORS for the Vite dev server, and
  a mock mode (`REROUTER_MOCK=1 uvicorn api.app:app`) answering from `fixtures/`.
  The generated OpenAPI schema is committed as `api/openapi.json` for the frontend
  client.
- Live REST API (`uvicorn api.app:app`, port 8000) on the simulation engine: the
  eight fixture scenarios by id (`01_normal` to `08_recovery`; mock mode now calls
  the diamond `07_diamond` too), inline scenarios including generator specs, all
  four policies, events, reset, `/compare` over the scenario's full event list, and
  the current step's decision record per flow. One run per session with its own
  lock; the oldest run is evicted at 64. Bad input from core (unknown policy, link,
  node, template or generator, bad generator parameters, exhausted generator
  retries) is 422 naming the value; unknown run, scenario or flow is 404. At 50
  nodes and 200 flows an event takes about 60 ms and returns about 144 KiB, of which
  decision records are 120 KiB.
