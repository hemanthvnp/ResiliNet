## 0. Facts D needs from cycle-1 code (checked on `main` at 6edee62)

- `Simulation(scenario, policy, cfg=None, check=False)` is in `core/sim/simulation.py`. It accepts a scenario file path, a dict or a `Scenario`, and a policy name or object. It routes step 0 on construction and ignores the scenario's events until you call `apply`, which is the healthy start the spec asks for. `apply(Event(step=..., kind="fail", links=[id]))` returns the post-failure `Snapshot`, and `reset()` returns to the healthy step 0.
- Scenario ids: `cli/main.py` `load(source)` takes a file path or a built-in id from `fixtures/scenarios/`. The diamond is `07_diamond`; the campus template is `01_normal` (topology `{"template": "campus"}`, no events). Reuse `cli.main.load` for `--scenario`, and do not copy `fixtures/` into `ext/`.
- The metrics are `snapshot.metrics.dr`, `.dr_by_class[0]` (DR_P0), `.overloaded_arcs` and `.unserved_by_cause["DISCONNECTED"]` (Metrics in `core/model/types.py`). A class with no flows is missing from `dr_by_class`; treat it as "no P0 traffic", not 0.
- Bridges: build an undirected `networkx` graph of the healthy topology's links and use `nx.bridges` (networkx is pinned at 3.5). `nx.bridges` rejects a `MultiGraph`, so build a simple `Graph`. Then drop any bridge whose node pair has more than one link, because a parallel link keeps the network connected.
- To check "healthy state restored", use `snapshots_identical([a], [b])` from `core/metrics/invariants.py`. It masks `compute_ms`, as the spec requires.
- pytest runs with `--import-mode=importlib`. If `import ext` fails under pytest, apply the `pythonpath` fix described in `ecmp-baseline` tasks section 0, in whichever cycle-2 branch merges first.
- The sweep lives in `ext/sweep.py`, and `ext/__main__.py` gets a `sweep` subcommand. If `ecmp-baseline` has merged, `ext/__main__.py` already exists; add the subcommand to it. If not, create it with `sweep` only, and the ECMP branch adds `run` and `compare` later.

## 1. Branch, review and tests first

- [x] 1.1 Create the branch `feat/criticality-sweep` from an up-to-date `main` after the cycle-2 plan PR is merged. Verify that `git log -1 main` matches `origin/main`.
- [x] 1.2 A human (D, or another member) re-works by hand the diamond and two-node numbers in `specs/criticality-sweep/spec.md`, and records "checked by <name>" in the PR description. Verify that every scenario value matches.
  - Checked by Nithiish (D): the diamond values (S2 10/15 and 10/25 after any single failure, S0-QoS unchanged) and the two-node value.
- [ ] 1.3 D sends `proposal.md`, `design.md` and the spec to ChatGPT for an adversarial review (PLAN-CYCLE2.md §6). Record each finding and its resolution in the PR. If a finding is accepted, update the spec and design first.
- [x] 1.4 D asks ChatGPT to write `ext/tests/test_sweep.py` from the spec scenarios only, pasting the facts in section 0 into the prompt. Commit the tests on their own. Verify that they fail only because `ext/sweep.py` does not exist yet.
  - Waived by D: D's agent wrote `ext/tests/test_sweep.py` from the spec scenarios, together with the code, instead of a different model writing it first.

## 2. Sweep

- [x] 2.1 In `ext/sweep.py`, implement the per-link fail, read and reset loop over one `Simulation` per policy, with links in ascending id order. Verify that the diamond S2, diamond S0-QoS and healthy-state-restored scenarios pass.
- [x] 2.2 Add bridge detection on the healthy topology, the structural and operational groups, the drop columns (healthy minus post-failure, per policy) and the shared-tie ranking. Exact ties share a rank, and link id only orders rows. Verify that the two-node structural, all-operational diamond and shared-rank scenarios pass.

## 3. Command and output

- [x] 3.1 Add `python -m ext sweep --scenario <file|id> [--policies ...] [--out file.csv]` to `ext/__main__.py`:
  - default policies are S2 and S0-QoS, plus ECMP-QoS if it is registered
  - CSV rows are sorted by policy, then link id
  - the printout shows every structural link and the top 5 operational links

  Verify the default-run (`--scenario 07_diamond` gives 8 rows), repeat-run (byte-identical CSV) and unknown-policy scenarios.
- [x] 3.2 Run `python -m ext sweep --scenario 01_normal --out results/sweep_campus.csv` (about 1 to 2 minutes per policy). Record the structural list and the top-5 operational table in the PR description. Add a "Single-link sensitivity" README paragraph using the PLAN-CYCLE2.md §4 wording. Verify that the documented command runs as written.

## 4. Integrate

- [ ] 4.1 Send the diff to Gemini or ChatGPT for an adversarial review. Fix accepted findings in the branch and record them in the PR.
- [x] 4.2 Run the full suite with `pytest`, and `check_invariants` on every snapshot the sweep produces on `01_normal` (pass `check=True` to each `Simulation`). Verify that all pass.
- [x] 4.3 Rebase onto `main`, run `sh .github/scripts/check-history.sh`, and open the pull request from `.github/pull_request_template.md`.
  - Done in #33.
