## 0. Facts D needs from cycle-1 code (checked on `main` at 6edee62)

- The registry is the dict `POLICIES` in `core/routing/registry.py`, read by `get_policy(name)` on every lookup. There is no `register()`. `ext/__init__.py` adds its policies with `POLICIES.setdefault("ECMP", Ecmp())` and `POLICIES.setdefault("ECMP-QoS", EcmpQoS())`. This changes only the in-memory dict, never the file, which is the fallback in PLAN-CYCLE2.md §7.
- A policy is any object with `name: str` and `route(topo, flows, prev, cfg, *, step=0) -> (Allocation, list[DecisionRecord])`. The protocol is `RoutingPolicy` in `core/model/types.py`, and `S0` in `core/routing/registry.py` is the pattern to copy. `Simulation(scenario, policy)` in `core/sim/simulation.py` also accepts a policy object directly.
- A's S0 and S0-QoS delivery (`core/routing/baselines.py`) handles one route per flow, and its helper `_route_baseline` is private. `ext/ecmp.py` therefore repeats the two formulas over several paths. S0 scales a path by min(1, capacity / load), taking the worst over its arcs. S0-QoS uses strict class priority per arc. Use exact `Fraction`s as `baselines.py` does, and convert to float only for the final `delivered`.
- `cli/main.py` already exposes `main(argv) -> int` with `run` and `compare` subcommands. `ext/__main__.py` imports `ext`, which registers the policies, and calls `cli.main.main(argv)` for `run` and `compare`.
- `check_invariants(snapshot, topology=, flows=, policy=, healthy_latency=, previous=, cfg=)` is in `core/metrics/invariants.py`. I4 (capacity) runs only for names in `CAPACITY_AWARE`, so it skips `ECMP` and `ECMP-QoS` with no extra code. `Simulation(..., check=True)` runs the invariants on every snapshot.
- `pyproject.toml` packages only `core*`, `api*` and `cli*`, and pytest runs with `--import-mode=importlib`, so `import ext` can fail under `pytest` even though `python -m ext` works from the repo root. Check this first (task 1.1). If it fails, add `pythonpath = ["."]` under `[tool.pytest.ini_options]` (or `"ext*"` to `[tool.setuptools.packages.find] include`) and say so in the PR, because `pyproject.toml` is shared. Do not change any version pin.

## 1. Branch, review and tests first

- [x] 1.1 Create the branch `feat/ecmp-baseline` from an up-to-date `main` after the cycle-2 plan PR is merged. Verify that `git log -1 main` matches `origin/main` and that `openspec/changes/ecmp-baseline/` exists. Also add an empty `ext/__init__.py` and check that `pytest --collect-only ext` can import `ext` (section 0); if it cannot, apply the `pythonpath` fix in the same commit.
- [x] 1.2 A human (D, or another member) re-works by hand the square, shared-first-hop, eight-path and diamond numbers in `specs/ecmp-routing/spec.md`, and records "checked by <name>" in the PR description. Verify that every scenario value matches the hand calculation.
  - Checked by Nithiish (D): square (8/7 and 5/5 split, F2 2 + 3 under strict priority), shared first hop (60/60, then 30/30), eight paths (13x4 + 12x4, excess 40, greedy gap 80 - 30 = 50) and the diamond equalities.
- [ ] 1.3 D sends `proposal.md`, `design.md` and the spec to ChatGPT for an adversarial review (PLAN-CYCLE2.md §6). Record each finding and its resolution in the PR description. If a finding is accepted, update the spec and design first.
- [x] 1.4 D asks ChatGPT to write `ext/tests/test_ecmp.py` from the spec scenarios only, without showing it any implementation. Paste the facts in section 0 into the prompt so the tests import the right names: `from ext.ecmp import Ecmp, EcmpQoS`, policies run through `Simulation`. Commit the tests on their own. Verify that `pytest ext/tests` fails only because `ext/ecmp.py` does not exist yet.
  - Waived by D: D's agent wrote `ext/tests/test_ecmp.py` from the spec scenarios, together with the code, instead of a different model writing it first.

## 2. Example data

- [x] 2.1 Add `examples/square.json`, `examples/shared-prefix.json` and `examples/eight-paths.json` as defined in the spec scenarios, with a test that each validates as a `Scenario` through `core.sim.scenario.load_scenario(path)`. Verify with `pytest ext/tests -k examples_load`.

## 3. Policy

- [x] 3.1 Implement the next-hop walk and the integer split per next hop in `ext/ecmp.py`:
  - next hops ordered by (node id, link id), at most 8 per router
  - each router sends `amount // n` to each next hop, and the remainder goes 1 Mbps at a time to the first next hops
  - branches that receive 0 are dropped

  Verify that the square, shared-first-hop and eight-next-hop scenarios in `test_ecmp.py` pass.
- [x] 3.2 Implement `ECMP` (proportional, as S0) and `ECMP-QoS` (strict priority, as S0-QoS) delivery per path by repeating the formulas (section 0). Add a test that the repeated formulas give the S0 and S0-QoS numbers on `fixtures/scenarios/07_diamond.json` for single-path flows. Verify that the square and diamond delivery scenarios pass.
- [x] 3.3 Register both names in `ext/__init__.py` via `POLICIES.setdefault`, and add `ext/__main__.py`, which hands `run` and `compare` to `cli.main.main(argv)`. Verify that `python -m ext compare --scenario examples/square.json --policies S0-QoS ECMP-QoS S2` prints DR 0.40, 0.80 and 0.80.
- [x] 3.4 Add a hypothesis test that runs `ECMP` and `ECMP-QoS` on random seeded campus scenarios through `Simulation(..., check=True)`, plus a repeat-run equality check with `snapshots_identical` from `core/metrics/invariants.py`. I4 is skipped automatically. Verify that it passes and prints the seed on failure.
- [x] 3.5 Add the eight-route regression test: ECMP-QoS 80, S0-QoS 10, S2 30 at `max_paths` 3 with cause `PATH_LIMIT` and greedy gap 50, and S2 80 at `max_paths` 8. Verify that it passes.

## 4. Docs

- [x] 4.1 Add an "ECMP-style baseline" paragraph to the README. It covers:
  - the idealised next-hop split
  - the fact that real routers hash whole flows
  - the square and eight-route results
  - why S2 is also reported at `max_paths` 8

  Use the PLAN-CYCLE2.md §4 wording. Verify that the documented commands run as written.

## 5. Integrate

- [ ] 5.1 Send the diff to Gemini or ChatGPT for an adversarial review. Fix accepted findings in the branch and record them in the PR.
- [x] 5.2 Run the full suite with `pytest`, and `check_invariants` on every ECMP snapshot of `examples/square.json` and the campus template. Verify that all pass.
- [x] 5.3 Rebase onto `main`, run `sh .github/scripts/check-history.sh`, and open the pull request from `.github/pull_request_template.md`.
  - Done in #36.
