# Network Rerouter: Cycle 2 Plan

Cycle 1 is [PLAN.md](PLAN.md), the team's 24-hour plan. It is frozen and this file does not change it. Cycle 2 adds a small, isolated set of features and documents in the last part of the hackathon, and records what is deferred to after it. Section numbers like "PLAN §9" refer to PLAN.md.

Status: design phase, revised after cross-model review (section 10). Open items are in section 8. The OpenSpec changes for this cycle are `submission-readiness`, `criticality-sweep` and `ecmp-baseline`.

---

## 1. Why a second cycle

Cycle 1 already covers the core of the problem statement: capacity-aware, priority-ordered rerouting, compared against shortest path (S0) and shortest path with QoS queues (S0-QoS), with per-flow explanations and a benchmark. A review of PLAN.md against three sources found what is left:

| Source | What it adds |
|---|---|
| Problem statement ("what would make it stand out") | Resilience scoring and the most critical link; minimum-disruption rerouting; graceful degradation; counts of critical flows served and nodes cut off; a dashboard of flows that changed paths |
| Feasibility research (campus SDN) | Compare against ECMP; claim an SDN-island deployment rather than whole-campus control; campus traffic peaks; selective rerouting; Ryu + Mininet (an emulator) as the path to a real deployment |
| CommitCon rulebook | Mandatory README fields (§8), AI-use disclosure (§6.5), demos with judge-chosen inputs (§9.5), explaining challenges (§9.4) |

The items that fit in the time left are in section 3. The rest is in section 5.

## 2. Constraints

- **Window: H16 to H20.** This is after the cycle-1 feature freeze and before rehearsal. **Blocker:** the team's CLAUDE.md allows only fixes and docs after H16. Cycle-2 *code* (sections 3.1 and 3.2) needs the team's explicit exception, recorded in the PR. Without it, only section 3.0 (docs and example data) and the wording in section 4 go ahead. Whatever is not finished and checked by H20 becomes a "next steps" line in the pitch.
- **Additive only.** No edits to cycle-1 modules, `core/model/types.py`, `fixtures/`, the OpenAPI schema or `frontend/`. New code lives in `ext/` and new data in `examples/`. Anything that needs a contract change is out of scope.
- **Cycle-1 numbers stay authoritative.** The H16 benchmark (PLAN §12) is the source for every cycle-1 claim. Cycle-2 numbers come from their own runs on the frozen code plus `ext/`, and are labelled as such.
- **Team rules apply** (CLAUDE.md): `feat/<change>` branches, PRs with green CI, no AI attribution in commits, no squash merges, never rewrite `main`.
- **Prepare before H16.** Proposals, reviews and tests written from the specs touch no frozen file. That leaves H16 to H20 for implementation only.
- **Timing.** The committed items (3.0, 3.2, 3.1) total about 4.5 hours of work. Preparing them before H16 brings the in-window work under 4 hours. Section 3.4 is optional.

## 3. Scope, in priority order

The order favours demo value: the rulebook items first, then the feature the problem statement names as standout, then the judge-question answer.

### 3.0 Submission readiness (about 1 hour, docs and data; mostly before H16)
- **README fields required by the rulebook (§8).** Cycle 1 already covers setup and run instructions and the solution description (PLAN §15 and D's README tasks). These are missing; D, who owns the README and the cycle-2 work, writes them:
  - team name and members
  - the selected problem statement (Problem Statement 4)
  - technologies and tools
  - significant external resources, with licenses checked against each project's LICENSE file
  - significant AI-tool use: each member's tools and what they were used for
  - a running "Challenges" list
- **Judge kit (rulebook §9.5):** editable scenario files under `examples/`, not `fixtures/`, which is frozen:
  - a custom P0 flow between two named buildings
  - a custom failure set
  - an overload case
  - the small hand-worked topologies from §3.1

  Each runs with one command, `python -m cli run --scenario examples/<file>.json --policy S2`, or with `POST /runs` and an inline scenario. Both already exist in cycle 1.

### 3.2 Single-link sensitivity sweep (about 2 hours)
**Why:** "resilience scoring" and "flag the single link whose loss would hurt most" are standout items in the problem statement.

**Method:**
- For each link of the scenario's healthy topology, in sorted id order: fail only that link, take the snapshot, then reset.
- Per policy, record post-failure `DR_P0`, `DR` and overloaded arcs, the **drop** from that policy's healthy `DR_P0` and `DR`, and the demand left unreachable (`DISCONNECTED`).
- **Two results, both shown:**
  - **Structural criticality:** bridges, the links whose failure splits the network, with the demand each one disconnects. This damage does not depend on routing, but these can be the most important links on campus.
  - **Operational criticality:** the remaining links, ranked by lowest post-failure `DR_P0`, then lowest `DR`. Exact ties share a rank. Link id only orders the rows.
- **Comparing policies uses both absolute and drop values, side by side.** Absolute values say how much service remains; drop values say how much the failure cost. On the PLAN §4 diamond:
  - S2 goes from 1.00 to 0.667 on critical traffic.
  - S0-QoS stays at 0.667.
  - Same service after the failure, different degradation. Neither number alone is the full picture.
- Default policies: S2 and S0-QoS, plus `ECMP-QoS` if §3.1 lands.

**Output:** a CSV and a printed table per policy (top 5 operational links and every bridge). No chart, because the frontend is frozen. Runtime: about 1 to 2 minutes per policy on the campus template.

**Scope of the claim:** a single-link sensitivity analysis for one topology, traffic matrix and policy configuration. It does not establish resilience to simultaneous failures, which is cycle 3's k-failure experiment (section 5).

### 3.1 ECMP-style baseline (about 1.5 hours)
**Why:** both the problem statement and the research name ECMP as the common load-spreading technique. "Why not just ECMP?" is a likely judge question.

**Definition:** an ECMP-*style*, idealised equal split per next hop (details in `openspec/changes/ecmp-baseline/`).
- **Equal-cost next hops:** at each router, the neighbours on a latency-shortest path to the destination. Parallel links count separately and are ordered by (node id, link id). At most 8 per router, a fixed width; sensitivity is reported, see below.
- **Integer split per next hop:** the traffic arriving at a router is divided as `amount // n` per next hop, with the remainder going 1 Mbps at a time to the first next hops. Branches that receive 0 Mbps are dropped. Path rates stay integers, so the frozen contract (`PathAlloc.rate: int`) is unchanged, and a flow has at most `rate` paths.
- **Delivery:** reuses the cycle-1 single-pass models, applied per path.
  - `ECMP`: proportional, as in S0.
  - `ECMP-QoS`: strict priority, as in S0-QoS.
- Registered by name in `ext/`. The UI, the API and the H16 benchmark are not changed.

**What this is not:** real routers hash whole flows to next hops, so they do not split rates exactly. This baseline is an idealised fluid approximation for aggregate flows. It is not a reproduction of any router's ECMP, and it is described that way.

**Hand-worked cases:**

| Topology | S0-QoS | ECMP-QoS | S2 (default `max_paths` 3) | S2 with `--max-paths 8` |
|---|---|---|---|---|
| Square: A–B, B–D, A–C, C–D, capacity 10, latency 1. F1 P0 15, F2 P2 10, both A→D | DR 0.40, 2 overloaded arcs | DR 0.80, DR_P0 1.00, 4 overloaded arcs | DR 0.80, DR_P0 1.00, 0 overloaded | same as default |
| Eight parallel paths: S→Ri→T for i = 1..8, capacity 10, latency 1. One P0 flow, 100 Mbps | DR 0.10, 2 overloaded arcs | DR 0.80, 16 overloaded arcs | **DR 0.30**, 0 overloaded, 70 unserved with cause `PATH_LIMIT` | DR 0.80, 0 overloaded |

**ECMP-QoS can beat S2.** On the eight-path case it delivers 80 against S2's 30, because S2's default allows at most 3 paths per flow. This is not a bug to hide:
- S2's decision log reports the shortfall itself: cause `PATH_LIMIT`, with a greedy gap of 50 Mbps that could have been routed.
- With `--max-paths 8`, S2 delivers the same 80 with no overloaded link.
- It is kept as a regression test, and the comparison is always reported at both path limits.

**Expected result** (stated before running, reported either way):
- On the campus network, ECMP-QoS overloads links wherever S2 overloads none.
- Delivery can go either way. Delivery and overload are reported as separate outcomes, never combined into one score.

### 3.3 SDN-island positioning (wording only)
The research classes "a controller of every campus switch" and hyperscaler-style central traffic engineering as infeasible for a campus. Cycle 1 assumes a central controller with global knowledge, so the README and the pitch state the scope:
- The current deliverable is a steady-state **simulation** of the controller's decisions.
- The intended deployment is an SDN island at the aggregation and core layer, which the campus template models, with aggregate flows (building × class, about 200), not per-user rules.
- Path to deployment, which is **future work and not built:** compute routes here, install them through an SDN controller (Ryu, or its maintained fork os-ken) on Open vSwitch. Validate first in Mininet, a network emulator, then on an SDN island beside legacy switches.

### 3.4 Campus traffic profiles (about 1 hour, optional)
Preset scenario files for campus load peaks: exam hour (P0 and P1 heavy), hostel evening (P2 bulk heavy), software-update window (P2 surge). Data only, under `examples/`. No algorithm change.

## 4. Pitch and demo wording (no code)
Revised after review (section 10) so that every claim is one the numbers support.

| Topic | Say | Avoid |
|---|---|---|
| S2's priority | "On every event S2 reallocates capacity in priority order: critical traffic first, lower classes get what is left. That is preemption at the allocation level, not packet-level preemption." | "S2 preempts packets" |
| Graceful degradation | "Lower-priority flows are served partially before they are dropped, so they slow down before they disappear." This is true of S2's splitting today. | Claiming per-flow minimum rates (cycle 3) |
| S0 | "A capacity-blind shortest-path baseline. It reroutes after a failure but does not check capacity. Fast reroute has the same blind spot, which is why we compare against it." | "S0 is fast reroute" |
| ECMP | "An idealised ECMP-style equal split. It can overload links; S2 never does. S2's path limit can leave deliverable traffic unserved, and its decision log says so. We report delivery and overload separately, including the cases where ECMP delivers more." | "Ours always beats ECMP" |
| Sweep | "For this topology, traffic and policy, this is the single link whose failure leaves critical traffic worst off. Links that disconnect part of the campus are listed separately." | "The most critical link in the campus", or anything about cascading or multiple failures |
| SDN | "A simulation of the controller, with a designed path to an SDN island." | Implying it already controls switches |
| Overall | "A capacity-safe, priority-ordered greedy allocator, compared fairly against capacity-blind baselines, with delivery, overload and failure impact reported separately." | "Optimal routing" |

## 5. Deferred to cycle 3 (after the hackathon)

| Item | Why deferred |
|---|---|
| Minimum-disruption (sticky) rerouting with priority preemption, plus a count of rule updates per event | The main algorithmic follow-up, 3 to 4 hours. It needs either a `PolicyConfig` change (frozen contract) or a policy that reads the previous allocation, which the cycle-1 `RoutingPolicy` interface forbids. |
| Metrics `p0_flows_served` and `nodes_cut_off`; a "rerouted" badge in the flow table | Need a contract or frontend change. They are possible in cycle 1 only if B and C add them before H1.5 and H12. |
| Per-flow minimum rate (graceful degradation for inelastic flows) | Contract change |
| k-failure resilience experiment (random sets of k simultaneous failures, stated seeds) | Answers "several failures at once"; the cycle-2 sweep is single-link only |
| Upstream-aware baseline delivery (PLAN §5) | Removes a known bias in favour of S2; listed for cycle 1 only if the core is stable at H12 |
| Ryu or os-ken + Mininet + Open vSwitch adapter | 8 to 12 hours, needs Linux root, Python version risk, demo-day risk. Rulebook §7.2 allows simulation. |
| Hybrid SDN-island model (only some links controllable) | Needs constrained path search |
| EWMA load prediction and time-varying traffic | Cycle 1 is steady state; see section 9 |
| Scaling study, LP reference | Already on the PLAN §14 roadmap |
| SNMP or sFlow ingestion, Prometheus/Grafana, Raspberry Pi testbed | Need real devices |

**Excluded** (agrees with the research): MPLS-TE, SRv6, ONOS or OpenDaylight, deep packet inspection, machine learning of any kind including deep reinforcement learning, and a full OpenFlow campus replacement.

## 6. How cycle 2 is built (multi-model workflow)
There is one OpenSpec change per item: `submission-readiness`, `criticality-sweep` and `ecmp-baseline` already exist under `openspec/changes/`. `campus-traffic-profiles` is proposed only if time is left. Each change goes through these steps:

1. Proposal, design and specs (Claude Code), before H16.
2. Spec review by a different model family: Gemini for compliance, ChatGPT for an adversarial technical review. Done once for this plan (section 10).
3. A human re-checks the hand-worked numbers. ChatGPT writes the tests from the spec, before H16.
4. Implementation by Claude Code until the tests pass, H16 to H20.
5. Adversarial review of the diff by Gemini or ChatGPT, never by the author model.
6. Deterministic checks: pytest, hypothesis property tests, `check_invariants`, CI.
7. A human reads the whole diff and can explain it (rulebook §6.4). PR, merge, archive.

Every tool used is listed in the README's AI section (rulebook §6.5), since commits carry no AI attribution.

## 7. Where the code lives and what it needs from cycle 1

**Folders.** All cycle-2 code lives in a new top-level `ext/` folder and example data in `examples/`. No member's folder is edited, and code is not put into A's or D's folder after their freeze. `ext/` and `examples/` are owned by D, who also owns `cli/` and the README.
- `ext/` imports `core/` and `cli/` but is imported by neither.
- `python -m ext run|compare|sweep` registers the ECMP policies, then hands `run` and `compare` to the cycle-1 CLI unchanged.
- `ext/` keeps the same purity rule as `core/`: no FastAPI or frontend imports.

**Small requests to cycle-1 owners** (wanted before the H16 freeze; none touches the contract):

| Owner | Request | Fallback if not done |
|---|---|---|
| A | The policy registry accepts new names at import time, for example a `register(name, policy)` function next to the S0 to S2 entries | **Fallback taken:** there is no `register()`; `ext` adds its policies to the `POLICIES` dict in `core/routing/registry.py` at import |
| A | The S0 and S0-QoS delivery models are callable on any allocation, including flows with several paths | **Fallback taken:** delivery is single-route and private (`_route_baseline`); `ext` repeats the two formulas, tested against the S0 and S0-QoS diamond numbers |
| D | The CLI entry point is a function, `main(argv)`, not only a `__main__` block | **Already in place:** `cli/main.py` defines `main(argv)` |

**Capabilities.** Cycle-2 OpenSpec changes add **new** capabilities only (`ecmp-routing`, `criticality-sweep`, `judge-kit`). None modifies a cycle-1 capability, so they can be archived after the nine cycle-1 changes in any order.

## 8. Open items before cycle 2 starts
1. **Team exception for the freeze (blocker for 3.1 and 3.2):** all four members agree that `ext/`-only code may land until H20. Otherwise those sections become pitch "next steps". **Agreed;** recorded in CLAUDE.md.
2. **Team membership:** every cycle-2 contributor must be a registered member of this team (rulebook §1, §10).
3. **Ownership of `ext/` and `examples/`** recorded in CLAUDE.md by the team. **Done:** assigned to D, in CLAUDE.md, AGENTS.md and the OpenSpec config.
4. **Hand-worked numbers:** the expected values in the cycle-2 specs were worked out by the spec author and checked again in review (section 10). A human re-checks them by hand before any test uses them (team testing rule), and the implementation is not written by the model that writes the tests.

## 9. Concepts the presenters must be able to explain

The project uses **no machine learning**, and none is planned before cycle 3. PLAN §6 excludes it and this plan keeps it out. What the team will be asked about is algorithms and a little statistics:

| Concept | Where | Difficulty | One-line explanation to prepare |
|---|---|---|---|
| Dijkstra shortest path | S0, S2 | Easy | Cheapest path by latency |
| Residual capacity, splitting | S2 (PLAN §5) | Easy | Send what fits on the best path with free capacity, then try the next best |
| Max-flow / min-cut | Decision log (PLAN §5, §10) | Medium | The most a flow could get; the cut is the set of full or failed links that blocks the rest |
| Greedy gap | Decision log | Medium | How much more the flow could have had; non-zero means our heuristic or path limit left it unused |
| Strict priority per link | S0-QoS, ECMP-QoS | Easy | Each link serves P0 first, then P1, then P2 |
| Equal-cost multipath | §3.1 | Easy | Split traffic evenly over equally short next hops |
| Bridge (graph) | §3.2 | Easy | A link whose loss cuts the network in two |
| Fortz-Thorup congestion cost | S2 option (PLAN §5) | Medium | Links get more expensive as they fill up; a feature flag, dropped if the ablation shows no benefit |
| 95% bootstrap confidence interval | Benchmark (PLAN §9) | **Hardest: statistics, not ML** | Resample the 30 seeds many times. If 95% of the resampled average improvements are above zero, the improvement is not luck. |
| Property-based testing ("hypothesis") | Tests | Easy | Random networks are generated and every invariant is checked. "Hypothesis" is the testing library, unrelated to the hypotheses H1 to H5. |
| LP reference (optional) | PLAN §8 | Medium-hard, optional | A solver gives an upper bound on what any routing could deliver. Present it only if it is built. |
| EWMA prediction (cycle 3) | §5 | Easy, but not built | A moving average that weights recent load more. Simple statistics, not ML. Do not present it as built. |

## 10. Cross-model review log (Gemini compliance review, ChatGPT adversarial review)

| # | Finding | Decision |
|---|---|---|
| G1 | The README list lacks the problem statement, description and run instructions | **Partly accepted.** Description and run instructions are already in cycle 1 (PLAN §15). The problem statement and technologies are added to §3.0. |
| G2 | Code in H16 to H20 breaks the team's H16 freeze | **Accepted as a blocker.** It needs a team exception; without one, only §3.0 and §4 go ahead (§2, §8). |
| G3 | The unowned `ext/` folder breaks folder ownership; put the code in A's and D's folders | **Rejected in part.** Adding code to A's and D's frozen folders is the larger breach. `ext/` edits no one's folder, but its owner must be recorded (§7, §8). |
| G4 | Graceful degradation and minimum disruption are fully deferred | **Partly accepted.** Partial service already is graceful degradation and the pitch now says so (§4). Minimum disruption needs a contract or interface change, so it stays in cycle 3 (§5). |
| G5 | Build Ryu + Mininet, as the research recommends | **Rejected.** The research calls it feasible for a campus deployment, not for an extra 8 to 12 hours in a 24-hour event. Rulebook §7.2 allows simulation. It stays as the deployment path (§3.3). |
| G6 | 5.5 hours does not fit in 4 | **Accepted.** §3.4 is optional; the sweep now comes before ECMP; preparation moves before H16 (§2). |
| G7 | Mininet is an emulator, not a real network | **Accepted** (§1, §3.3). |
| C1.1 | Splitting per path is not ECMP; splitting per next hop differs when paths share a first hop | **Accepted.** Verified by hand: 120 Mbps over S–A–X–D, S–A–Y–D and S–B–D gives S–A 80 / S–B 40 per path, and 60 / 60 per next hop. Switched to an integer split per next hop (§3.1). |
| C1.2 | The cap of 8 is arbitrary; parallel links need a tie-break | **Accepted.** The cap is now a per-router width (a fixed choice, not a hardware claim); parallel links are tie-broken by link id; sensitivity is reported. |
| C1.3, C1.4 | It is not faithful ECMP; "the fair comparison" overstates it | **Accepted.** Renamed "ECMP-style, idealised" and the README wording changed (§3.1, §4). |
| C2.1 | ECMP-QoS can beat S2: eight parallel paths give ECMP-QoS 80, S2 30, S0-QoS 10 | **Accepted and verified by hand.** The cause is S2's `max_paths` 3; with 8 it delivers 80 with no overload. Kept as a regression test and a demo of the decision log (`PATH_LIMIT`, greedy gap 50). |
| C3.1 | The link-id tie-break looks like a criticality ranking | **Accepted.** Exact ties share a rank (§3.2). |
| C3.2 | Bridges can be the most critical links | **Accepted.** The structural and operational results are both shown (§3.2). |
| C3.3 | Single-link failures do not show resilience to multiple failures | **Accepted.** Labelled a single-link sensitivity analysis; the k-failure experiment is in §5. |
| C3.4 | Absolute delivery and drop measure different things | **Accepted.** Both are reported side by side (§3.2). |
| C4.1 to C4.5 | Pitch wording for preemption, S0 as fast reroute, ECMP, sweep scope, SDN | **Accepted.** Replaced by the §4 table. |
| C5 Q5 | The baseline's single-pass bias favours S2 | **Accepted, already disclosed** in PLAN §5. The upstream-aware version is listed in §5. |
