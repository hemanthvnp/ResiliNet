## Context

PLAN.md section 9 fixes one network size (about 50 nodes, 200 flows) and one generator. Section 13 lists "demo network does not show the story" as a risk, mitigated by tuning the template at H8 to H10 after S0-QoS and S2 both run. The diamond's second row shows why the check must be done after the failure: two paths before means one path after, which is a tie.

## Goals / Non-Goals

**Goals:**
- Same `(spec, seed)` always gives the same topology and flows.
- The demo template and every generated network pass the post-failure path check.
- The UI and the CLI use the same generator through `TopologySpec` and `TrafficSpec`.

**Non-Goals:**
- More than one generator family, real topology import, scaling study (roadmap, section 14).
- Time-varying traffic.

## Decisions

**Three-tier campus shape: core, distribution, building access.** Core routers form a small mesh; each building switch has a primary uplink and, with probability `redundancy`, extra uplinks to other distribution or core nodes. Key services (auth, emergency) hang off the core so P0 flows have meaningful destinations.
*Rejected:* random graphs (Waxman, Barabási-Albert), because they need a separate story for what "uplink" and "building" mean.

**The template is a JSON fixture; the generator is code.** The template is tuned by hand at H8 to H10 and is loaded through the same `TopologySpec` path (`{template: "campus"}`).
*Rejected:* producing the template by calling the generator with a fixed seed, because a change to generator code would then silently change the tuned demo network.

**Traffic demand is sized from `load_factor`.** Rates are drawn as integers, scaled so that total demand is about `load_factor` times the sum of building uplink capacities, and rounded to integers with a minimum of 1. The benchmark sweep multiplies each base rate by the sweep factor and rounds, so the same flows exist at every factor.
*Rejected:* regenerating traffic per factor, because the curves would then compare different flow sets.

**Class counts are exact, not sampled.** `class_mix` shares are turned into counts by largest-remainder rounding, then flows are assigned classes in id order.
*Rejected:* drawing each flow's class at random, because small runs would then miss P0 flows on some seeds.

**The path check is one function, used by the template test and by the generator.** It fails the designated primary uplink on a copy, then for each building takes node-disjoint paths to the core (networkx) and compares their combined bottleneck capacity with the building's P0 plus P1 demand. Because it needs demand, the generator checks topology and traffic together.
*Rejected:* a separate check in the generator, because two definitions of "traffic has somewhere to go" can drift apart.

**Retry is bounded at 20 seeds and the effective seed is returned.** On a failed check the generator moves to `seed + 1`, then raises with the last failure reason.
*Rejected:* failing on the first bad seed, because a user typing a seed into the UI would then often get an error; section 9 specifies the retry.

**Determinism.** Every random draw goes through one `random.Random(seed)` created from the spec and passed down explicitly; topology and traffic take separate seeds so traffic can vary on a fixed network. Ids come from counters (`N1`, `L1`, `F1`), candidate lists are sorted by id before any draw, and the retry sequence is `seed, seed + 1, ...`. The check iterates buildings in id order so its failure message is stable.
*Rejected:* the module-level `random` functions with `random.seed`, because that is global state: a draw made anywhere else would shift every later result.

## Risks / Trade-offs

- [The tuned template only ties S0-QoS] → This is assumption A2. B retunes at H8 to H10 by adding a second, longer path with spare capacity; the fallback pitch is in section 12.
- [Retry changes the seed silently] → The effective seed is recorded in the returned scenario and shown in the UI.
- [Rounding after scaling changes total demand slightly] → Accepted; the benchmark reports the realised total demand, not the nominal factor.
- [Tuning edits a frozen fixture] → All four members agree first, and the fixture changes before the code that reads it.
- [Node-disjoint path check is slow] → It runs once per generated network at about 50 nodes, outside the recompute path.
