## 1. Branch and property tests (D, H4 to H8)

- [ ] 1.1 Create the branch `feat/add-cli-benchmark` from an up-to-date `main`
- [ ] 1.2 Add a hypothesis strategy in `tests/property/` that draws a seed, size and event list and builds a scenario through the generators, with a test asserting I1 to I10 through B's checker on every snapshot for all four policies, under a fixed derandomized profile
- [ ] 1.3 Make a failing property test print the seed and parameters for replay, with a test of the message on a forced failure
- [ ] 1.4 Add I11 to the property test once decision records carry the cut and the bound

## 2. CLI (D, H4 to H8)

- [x] 2.1 Add `cli/main.py` with shared scenario and config arguments and the `run` subcommand (snapshot sequence to JSON, headline metrics to stdout), with tests: the diamond under S2 exits 0 with valid output, an unknown policy exits non-zero and names it
- [x] 2.2 Add the `compare` subcommand with the default policy list, with a test that the diamond gives four rows and the S2 row shows `DR` 0.80 and 0 overloaded arcs at the healthy step
- [ ] 2.3 Add the config flags (`--order`, `--max-paths`, `--lambda`, `--util-cap`), with a test that a path limit of 1 reports F1 as `PATH_LIMIT`
- [x] 2.4 Add a test that two runs of the same generator spec and seed write identical output once `compute_ms` is masked, and a test that `cli/` does not import `api`

## 3. Benchmark runner (D, H8 to H12)

- [ ] 3.1 Add per-seed case generation (`healthy`, `uplink`, `multi`, `recovered`) with failures drawn from a per-purpose seeded RNG over sorted link ids, with tests: the same seed gives the same failure set, every policy sees the same failed links and total demand
- [ ] 3.2 Add the load-factor sweep and the one-knob ablation variants, with tests: six factors per policy, each variant differs from the default in exactly one knob
- [ ] 3.3 Write the long-format CSV (sorted rows) and the summary JSON (config, commit hash, reductions), with a test that a 2-seed benchmark is reproducible and has every policy for every case
- [ ] 3.4 Time the first seed and apply the matrix-sizing rule, with a test that a projected overrun cuts the ablations and records it
- [ ] 3.5 Measure the median `compute_ms` at demo size for H4 and report it to A (assumption A3)

## 4. Statistics and hypotheses (D, H12 to H16)

- [ ] 4.1 D writes a tiny CSV by hand with its expected mean, median and paired difference, committed as `tests/cli/expected_stats.json`. An agent does not produce these values
- [ ] 4.2 Add mean, median and the seeded 95% bootstrap interval in `cli/stats.py`, with tests from `expected_stats.json` and a test that the interval is identical on repeat
- [ ] 4.3 Add the paired S2 minus S0-QoS difference per seed, with a test from `expected_stats.json`
- [ ] 4.4 Add the H1, H1b, H2, H3, H4 and H5 evaluations with measured values and pass or fail, with tests: H1 passes at 10 points, fails below, H5 lists the runs with a non-zero gap
- [ ] 4.5 Run the full benchmark, commit the results tables under `results/`, and draft the results section
- [ ] 4.6 Rerun once at the H16 freeze on the frozen code and replace the tables; only this run's numbers are used

## 5. README and demo deliverables (D, H16 to H22)

- [ ] 5.1 Write the README setup (one command for the backend, one for the frontend) and verify it on a clean machine
- [ ] 5.2 Write the model, assumptions, algorithm with pseudocode and architecture diagram sections
- [ ] 5.3 Write "reproduce a run from a seed" and the benchmark results with the stress-case mapping
- [ ] 5.4 Write the limitations section (ties and losses against S0-QoS, the single-pass baseline bias, greedy sub-optimality), the technical-contribution paragraph and future work
- [ ] 5.5 Fill the demo script with numbers from the final run and save the fallback run JSON with `compare --out`
- [ ] 5.6 Record the fallback video

## 6. Integrate

- [ ] 6.1 Run the full test suite with `pytest`, and `check_invariants` on every snapshot of the fallback run
- [ ] 6.2 Rebase onto `main`
- [ ] 6.3 Run `sh .github/scripts/check-history.sh`
- [ ] 6.4 Open the pull request from `.github/pull_request_template.md`
