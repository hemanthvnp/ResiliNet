# Changelog

Notable changes to this project, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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
- `AGENTS.md` with the rules shared by every member's coding agent.
