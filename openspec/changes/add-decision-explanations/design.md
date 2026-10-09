## Context

The allocator has no reverse arcs, so it is not a max-flow algorithm: an early push can block capacity a later push needed, and `max_paths` limits it further. PLAN.md section 5 exposes this weakness instead of hiding it, by attaching `maxflow_bound` and `greedy_gap` to every unserved flow. Section 10 defines the record, the cut and the explanation template.

## Goals / Non-Goals

**Goals:**
- A record for every flow under every policy, matching the frozen `DecisionRecord` model.
- The cut is presented as the reason only when `greedy_gap` is 0.
- Explanations are deterministic and diffable between runs.

**Non-Goals:**
- Enumerating alternative paths.
- Free-text or generated-language explanations.
- Changing the allocation. This module only describes it.

## Decisions

**A builder in `core/explain/`, called by the policies.** The policy passes facts (flow, step, failed links, previous paths, reference path, attempts, delivered, cause, and for the allocator the ledger). The builder returns a `DecisionRecord`.
*Rejected:* building records inside the allocator, because the allocator must stay small enough to walk through line by line, and the baselines need the same builder.

**"Alternatives considered" comes from three recorded facts.** The reference path (latency-shortest, ignoring capacity) with a status, each residual-graph attempt, and the cut. Reference statuses are fixed strings: `USED`, `PARTIAL: <arc> saturated`, `INVALID: <link> down`, `NONE: disconnected`.
*Rejected:* enumerating k shortest paths (Yen) to list candidates, because section 3 rules it out: the candidates may all be congested and k is a guess.

**The cut is the set of arcs leaving the residual-reachable set of the source.** Reachability uses arcs with residual above zero. An arc from a reachable node to an unreachable one is in the cut, with state `saturated` (available, residual 0) or `down`. `load_by_class` comes from `Ledger.class_breakdown` and includes the flow's own load. The cut is computed only for `INSUFFICIENT_CAPACITY`.
*Rejected:* taking the minimum cut from the max-flow computation, because that cut can lie elsewhere than where the greedy placement actually stalled, and it is not available when the bound is lazy.

**The bound uses the ledger as it was when the flow was placed.** `pre` is the residuals at the end of the flow's placement with the flow's own reservations added back. `maxflow_bound = min(rate, maxflow(pre, src, dst))` and `greedy_gap = maxflow_bound − delivered`. It is computed for every unserved S1/S2 flow, including `PATH_LIMIT`. For `DISCONNECTED` both are 0.
*Rejected:* a bound on the empty network, because it would blame the heuristic for capacity that higher classes legitimately hold.

**Lazy bound as a cut line.** If recompute takes 1 second or more, records are emitted with `maxflow_bound` and `greedy_gap` unset, and a function computes them on request by replaying the allocation in order up to that flow. The benchmark computes them offline.
*Rejected:* dropping the bound when it is slow, because the max-flow check is one of the three visible differentiators (section 13).

**Explanation is a fixed template over record fields.** Segments: header `F12 (P0, 15 Mbps):`; reference status; one "Moved N Mbps to <path> (latency L ms)" per attempt; then the unserved segment. With `greedy_gap` 0 and a cut: `N Mbps unserved: cut <links> saturated by <classes> (<rate> Mbps)`. With `greedy_gap` above 0: `N Mbps unserved, of which G Mbps could have been routed (heuristic or path limit)`. Baselines use `OVERLOAD_LOSS` and `DISCONNECTED` segments. Paths are printed as node sequences (`A-C-D`).
*Rejected:* free text or a language model, because the text must be identical between runs and checkable against the record.

**Baseline records fill a subset of one record type.** S0 and S0-QoS fill `flow_id`, `cls`, `demand`, `step`, `reference_path`, `delivered`, `unserved`, `cause`, `explanation`; `attempts` and `cut` are empty and the bound fields are unset.
*Rejected:* a second record type for baselines, because the contract has one `DecisionRecord` and the UI has one decision panel.

**Determinism.** No randomness is used. Records are returned in the order flows were placed. Cut arcs are sorted by arc id and class keys ascend. The template prints whole-number rates without decimals and other rates with a fixed number of decimals, so the same record always gives the same string. The lazy replay runs the same deterministic allocator.
*Rejected:* emitting cut arcs in traversal order, because it would make two equal records differ as text.

## Risks / Trade-offs

- [Max-flow per unserved flow makes recompute slow] → Lazy mode above; measured at H8 on the first seed.
- [The cut is shown as a physical limit when the heuristic is to blame] → The template branches on `greedy_gap`; invariant I11 and a blocking-example test cover it.
- [Record fields drift from the frozen model] → The section 10 JSON fixture is a test input; the builder output for that case must equal it.
- [The lazy replay diverges from the eager value] → A test computes both on the fixtures and asserts equality.
