## Context

PLAN.md section 9 fixes one network size (about 50 nodes, 200 flows), 30 seeds, four policies, a load-factor sweep and ablations, and states the hypotheses before any run. Section 12 says any algorithm fix after a benchmark run invalidates its tables, so the final run happens once at H16 on frozen code. The scaling study is cut.

## Goals / Non-Goals

**Goals:**
- Any run is reproducible from a seed with one command.
- The benchmark finishes within 30 minutes or shrinks itself in a stated way.
- Hypotheses are evaluated by code and reported whether they pass or fail.

**Non-Goals:**
- Scaling study across sizes, extra generators, Monte-Carlo robustness curve (roadmap).
- Charts (the frontend draws them from the CSV).

## Decisions

**Three subcommands on one entry point, `python -m cli`.**
- `run --scenario <file|id> --policy <name> [--out file]` writes the snapshot sequence as JSON and prints the headline metrics.
- `compare --scenario <file|id> [--policies ...] [--out file]` prints one table row per policy.
- `benchmark [--seeds N] [--out dir] [--no-ablations]` writes CSV and a summary JSON.

Config knobs are flags (`--order`, `--max-paths`, `--lambda`, `--util-cap`).
*Rejected:* three separate scripts, because argument parsing and scenario loading would be written three times.

**Stress cases are generated per seed and mapped to the fixture scenarios they resemble.** H1 and H1b name stress scenarios 2 to 5 and H2 names scenarios 1 and 8. For each seed the benchmark builds a campus network and derives four cases: `healthy` (no failure, like 1), `uplink` (fail the primary uplink, like 2), `multi` (fail three random links, like 3), `recovered` (fail then recover, like 8). The load-factor sweep above 1.0 gives the insufficient-capacity regime of scenario 5. H1 and H1b use `uplink` and `multi`; H2 uses `healthy` and `recovered`. This mapping is an interpretation of section 9 and is stated in the README.
*Rejected:* evaluating the hypotheses on the eight fixtures alone, because each is a single deterministic run and a confidence interval needs many.

**Failure sets are random draws, independent of any policy.**
*Rejected:* failing the most loaded links, because load depends on the policy and the conditions would no longer be identical across policies.

**One long-format CSV row per `(seed, case, load_factor, policy, variant)`** with every metric as a column; `variant` names the ablation (`default`, `order=arrival`, `max_paths=1`, and so on).
*Rejected:* a wide table with one column group per policy, because the tables and the frontend chart would each have to reshape it.

**Paired statistics.** The H1 quantity is the per-seed difference `DR(S2) − DR(S0-QoS)`, reported as mean, median and a 95% bootstrap interval over seeds. H1 passes when the mean difference is at least 10 percentage points and the interval lies above zero.
*Rejected:* separate intervals per policy, because that ignores the identical conditions and gives a wider interval for the same data.

**The matrix sizes itself.** The first seed is timed across the full matrix. If the projection exceeds 30 minutes, ablations are cut to `max_paths` and `congestion_lambda`; if still over, to 10 seeds with no ablations (the H12 cut line). The summary records the reduction.
*Rejected:* a fixed matrix, because an overrun discovered at H14 would leave no results at the H16 freeze.

**`compute_ms` for H4 is the median of repeated runs** on one seed at default size, kept out of every correctness check.
*Rejected:* the mean, because one slow run on a busy laptop would move it.

**The summary records the git commit hash and the config.**
*Rejected:* results files with no provenance, because the rule that spoken numbers come from the frozen code could not be checked.

**Property tests call B's checker.** Hypothesis draws small seeds and sizes, builds a scenario through the generators with a random event list, and asserts the invariants for every policy.
*Rejected:* assertions written inside the property tests, because the invariants would then have two definitions.

**Determinism.** Seeds are the fixed list `0..N-1`. Each random purpose gets its own `random.Random` built from an integer derived by arithmetic from the seed (for example `seed * 1000 + purpose`), never from `hash()`, which Python randomizes per process. Failure sets are drawn over link ids sorted first. The bootstrap uses a fixed seed and 10 000 resamples. CSV rows are written sorted by `(seed, case, load_factor, policy, variant)`. Hypothesis runs with a fixed derandomized profile in CI so a failure reproduces.
*Rejected:* one shared RNG for the whole benchmark, because adding a case or an ablation would shift every later draw.

## Risks / Trade-offs

- [The matrix is too slow] → Timed first, then reduced by the stated rule.
- [H1 fails or S2 only ties] → Reported as it is, with the scenarios where it ties listed in the README limitations section.
- [30 seeds give a wide interval (A4)] → The interval is reported as it is.
- [A late algorithm fix makes tables stale] → One final rerun at H16; the summary's commit hash must match the tagged code.
- [The stress-case mapping is questioned] → It is documented, and the eight fixtures remain as exact single runs.
- [D is overloaded] → B takes the benchmark run from H12, at D's request.
