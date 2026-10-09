# Changelog

Notable changes to this project, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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
  Live mode answers 501 until the simulation engine lands. The generated OpenAPI
  schema is committed as `api/openapi.json` for the frontend client.
