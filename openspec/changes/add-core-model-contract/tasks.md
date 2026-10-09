## 1. Branch and skeleton (B, H0 to H0.5)

- [x] 1.1 Create the branch `feat/add-core-model-contract` from an up-to-date `main`
- [x] 1.2 Add `pyproject.toml` (Python 3.11+, pinned pydantic v2, networkx, pytest, hypothesis) and the empty packages `core/model`, `core/gen`, `core/routing`, `core/sim`, `core/metrics`, `core/explain`, with one import smoke test in `core/model/tests/` so `pytest` passes
- [x] 1.3 Write `AGENTS.md` (stack, folder ownership, determinism rules of section 7, test command, "never edit `core/model/types.py` or `fixtures/`"); point `CLAUDE.md` to it and record the install and test commands there

## 2. Types (B, with A on DecisionRecord, H0.5 to H1.5)

- [x] 2.1 Add `Node`, `Link`, `Topology`, `Flow` to `core/model/types.py`, with tests that a non-integer capacity or rate is rejected
- [x] 2.2 Add `PathAlloc`, `FlowResult`, `Allocation` with float `delivered` and `unserved`, with tests for a fractional delivery and an unknown cause
- [x] 2.3 Add `PolicyConfig` and `Event`, with a test of the section 7 defaults
- [x] 2.4 Add `Attempt`, `CutArc`, `DecisionRecord` (A and B together), with a test that `{"0": 10}` loads as `{0: 10}`
- [x] 2.5 Add `Metrics`, `TopologySpec`, `TrafficSpec`, `Scenario`, `Snapshot` and the `RoutingPolicy` protocol, with a test that no model has an `Any` field

## 3. Arc model and ledger (B, H0.5 to H1.5)

- [x] 3.1 Add `core/model/arcs.py` (expand links to arcs, arc id format, parse arc id, available-arc filter, sorted output), with tests: link gives two arcs, down link gives none, order is stable
- [x] 3.2 Add `Ledger` construction and `residual` in `core/model/ledger.py`, with tests: fresh ledger, `util_cap` 0.9 on capacity 15 gives 13, down arcs excluded
- [x] 3.3 Add `bottleneck` and `reserve` (raises and changes nothing on overflow), with tests for both outcomes
- [x] 3.4 Add `release` and `class_breakdown`, with tests: release restores capacity, breakdown by class in ascending order

## 4. Fixtures and freeze (B, by H1.5)

- [x] 4.1 B writes the diamond topology and flows (section 4) as a fixture by hand, with a test that it validates
- [x] 4.2 B writes one snapshot per policy for the diamond by hand from the section 4 table, with a test that each validates
- [x] 4.3 B writes the S0 snapshot with a non-integer `delivered` (a 7 Mbps flow scaled by 0.4) by hand, with a test that 2.8 and 4.2 are preserved
- [x] 4.4 Save the section 10 decision-record JSON as a fixture, with a test that it validates as a `DecisionRecord`
- [x] 4.5 Add the freeze test: import every section 7 name and validate every file under `fixtures/` against its model
- [x] 4.6 All four members confirm the contract in chat once the freeze test passes; record the freeze in `CHANGELOG.md`

## 5. Integrate

- [x] 5.1 Run the full test suite with `pytest`. `check_invariants` does not exist until `add-metrics-invariants`; the freeze test is the gate for this change
- [x] 5.2 Rebase onto `main`
- [x] 5.3 Run `sh .github/scripts/check-history.sh`
- [x] 5.4 Open the pull request from `.github/pull_request_template.md`
