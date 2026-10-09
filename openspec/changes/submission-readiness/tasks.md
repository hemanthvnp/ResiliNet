## 0. Facts D needs (checked on `main` at 6edee62)

- **There is no `README.md` on `main` yet.** D creates it, and the cycle-1 README tasks (`add-cli-benchmark` 5.1 to 5.5) fill the setup, model, results and demo sections of the same file. Write these cycle-2 sections into that one README, and add no second file.
- A scenario file has the shape of `fixtures/scenarios/01_normal.json` under its `"scenario"` key: `id`, `seed`, `topology` (`{"template": "campus"}`), `traffic` (a list of flows `{id, src, dst, rate, cls, service}`), `events` and `config`. An example file holds that object at the top level. Check it with `core.sim.scenario.load_scenario(path)`.
- Node ids for the campus template come from the topology the template builds. Read them from `python -m cli compare --scenario 01_normal --policies S2 --out /tmp/n.json`, whose `topology` key lists every node and link. `run --out` writes only the snapshot list. Do not guess the ids.
- Load factor 1.5 uses the generated traffic spec (`GeneratedTrafficSpec` in `core/model/types.py`: `generator`, `n_flows`, `load_factor`, `class_mix`, `seed`). Give it an explicit seed.
- Tests go in `ext/tests/test_examples.py`. pytest runs with `--import-mode=importlib`; see `ecmp-baseline` tasks section 0 if imports fail. Run each example in-process through `cli.main.main(["run", "--scenario", path, "--policy", name])`, which returns the exit status, and run invariants with `Simulation(path, name, check=True)`.

## 1. Branch

- [ ] 1.1 Create the branch `feat/submission-readiness` from an up-to-date `main` after the cycle-2 plan PR is merged. Verify that `git log -1 main` matches `origin/main`.

## 2. README sections (D, can start at any time)

- [ ] 2.1 Create `README.md` if it does not exist, and write the sections for team name and members, problem statement (Problem Statement 4) and technologies. Verify that they render on GitHub.
- [ ] 2.2 Write "External resources" with each direct dependency and its license, taken from `pyproject.toml` and `frontend/package.json`. Check every license against the project's own LICENSE file. Expected licenses:
  - backend: pydantic MIT, networkx BSD-3-Clause, FastAPI MIT, uvicorn BSD-3-Clause, pytest MIT, hypothesis MPL-2.0, httpx BSD-3-Clause, scipy BSD-3-Clause (optional, LP reference only)
  - frontend: React MIT, Vite MIT, Cytoscape.js MIT, Recharts MIT, lucide-react ISC, TypeScript Apache-2.0, Vitest MIT, Testing Library MIT, jsdom MIT, openapi-typescript MIT

  Verify that every direct dependency in the two manifests is listed.
- [ ] 2.3 Collect each member's AI tools and what they were used for, and write "AI tools used". This is the only AI disclosure, because commits carry none (rulebook §6.5). Verify that all four members have a line.
- [ ] 2.4 Start a "Challenges" list, one line per problem met during the hackathon, added as it happens. Verify that it has entries before the H20 rehearsal.
- [ ] 2.5 Add the "Scope" wording from PLAN-CYCLE2.md §3.3 (a simulation of the controller, an SDN island as the deployment path, Ryu or os-ken with Mininet as future work). Verify that no sentence claims the system controls real switches.

## 3. Judge kit

- [ ] 3.1 Add `examples/custom-flow.json` (`01_normal` plus one P0 flow between two named buildings), `examples/custom-failure.json` (three named links fail in one event, then one recovers) and `examples/overload.json` (campus template at load factor 1.5, explicit seed). Add a test that loads each one with `load_scenario`. Verify the files-validate scenario.
- [ ] 3.2 Add the test that runs every example under S0, S0-QoS, S1 and S2 with `check_invariants`. I4 applies to S1 and S2 only, and `Simulation(..., check=True)` handles that. Verify that the all-examples scenario (12 runs) passes.
- [ ] 3.3 Add the edited-priority test (the added flow changed to P2 is reported with class 2 under S2) and the mistyped-link test (a non-zero exit, with the error naming the bad id). Verify that both pass.
- [ ] 3.4 Write the "Try your own input" README section: one `python -m cli run --scenario examples/<file>.json --policy S2` command per example, and which fields to edit. Verify that every documented command runs as written.

## 4. Integrate

- [ ] 4.1 Run the full suite with `pytest`. Verify that it passes.
- [ ] 4.2 Rebase onto `main`, run `sh .github/scripts/check-history.sh`, and open the pull request from `.github/pull_request_template.md`.
