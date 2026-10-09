## Context

The repo has no code. PLAN.md section 7 lists the models and interfaces and section 11 makes them a human-edited contract frozen at H1.5. Deliveries are integers under S1 and S2 but fractional under S0 and S0-QoS (a rate times a scale factor), which is the detail most likely to be modelled wrongly in the first hour.

## Goals / Non-Goals

**Goals:**
- Every type in section 7 exists as a pydantic model with no placeholder or `Any` field.
- A fixture of each type validates, including the float-delivery case and the section 10 decision record.
- `Ledger` enforces the capacity invariant at the point of reservation.
- All agents work from one instruction file.

**Non-Goals:**
- Generators, routing, simulation, metric formulas (other changes).
- The OpenAPI schema and API mocks (`add-rest-api`).
- Persistence of any kind.

## Decisions

**One `types.py` for all shared models.** Section 7 names the file, and a single file is easy to freeze and to hand to an agent as context.
*Rejected:* one file per model group, because the freeze rule would then be spread over several files.

**`delivered` and `unserved` are `float`; `PathAlloc.rate`, `Allocation.arc_load`, capacities, rates and latencies are `int`.** This follows section 2. Equality checks on the float fields use a tolerance of 1e-9.
*Rejected:* `Fraction` for exact baseline deliveries, because it does not serialize to plain JSON.

**Arc id is the string `"<link id>:<u>><v>"`.** It is readable in the decision log and sortable. Helpers in `core/model/arcs.py` build the arc list, parse an arc id back to its link, and filter to available arcs; no other module builds an arc id.
*Rejected:* a `(link, u, v)` tuple, because a tuple cannot be a JSON object key in `arc_load` and `load_by_class` records.

**`Ledger` lives in `core/model/ledger.py` and `reserve` raises on overflow.** B owns it and A consumes it from H1.5. It is built from the available arcs with `cap = floor(util_cap * capacity)`. `reserve` and `release` take the flow's class so that `class_breakdown` can attribute a cut; the two-argument signature in section 7 cannot do that.
*Rejected:* clamping and returning the amount reserved, because a silent clamp would hide an allocator bug that the invariant is meant to expose.

**`Ledger.release` is kept although the allocator never releases during placement.** Section 5 needs "residuals with the flow's own reservations added back" for the max-flow bound, and invariant I5 tests reserve/release symmetry.
*Rejected:* dropping `release` and rebuilding a ledger for each bound, because that replays every earlier flow once per unserved flow.

**Models are mutable pydantic models.** `Topology` link status is changed by the simulation. Purity is a rule on `RoutingPolicy.route`, checked by the determinism test.
*Rejected:* frozen models with copy-on-change, because every event would copy the topology and no check would be gained.

**Class keys are `int` in Python and strings in JSON.** Pydantic coerces on load; the section 10 fixture uses `{"0": 10}` and must validate into `dict[int, int]`.
*Rejected:* string keys such as `"P0"`, because section 7 types them as `int` and priority order is a numeric comparison.

**Unit tests sit beside the module, in `core/<module>/tests/`.** PLAN.md section 11 has every member test their own module, and gives the top-level `tests/` folder to D.
*Rejected:* one top-level `tests/` tree for everything, because each core change would then span two owners' folders. `tests/` holds D's cross-module suites only (API, CLI, property tests).

**Determinism.** No randomness is used. The arc list is sorted by arc id. `Ledger` stores arcs in that order and `class_breakdown` returns classes in ascending order, so nothing downstream depends on dict or set ordering.
*Rejected:* relying on dict insertion order, because it would tie results to the order links appear in a JSON file.

## Risks / Trade-offs

- [A type is missed and discovered after the freeze] → The freeze checklist is a test: it imports every name listed in section 7 and loads every fixture. The contract is frozen only when that test passes.
- [An agent edits `types.py` to make its own code pass] → `AGENTS.md` forbids it; changes need all four members and fixtures updated first.
- [Float fields drift into integer-only code paths] → The non-integer S0 fixture is in the first test run, so integer assumptions fail in hour 1.
- [The three-argument `reserve` differs from section 7] → Raised with A at H0 to 1.5, before the freeze, since A is the only caller.
- [networkx version changes tie-breaking] → Versions are pinned here; the tie-break rule itself is implemented in `add-routing-policies`.
