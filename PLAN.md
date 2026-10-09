# Network Rerouter (Problem Statement 4): Implementation Plan

Team: 4 members, each developing with an AI coding agent (rules in section 11). Time budget: 24 hours. Status: planning only, no code written.

Members are called **A** (routing algorithms), **B** (simulation and model), **C** (frontend), **D** (integration, metrics, QA).

---

## 1. Executive recommendation

Build a **steady-state fluid simulator of a campus network** with a centralized routing controller. The user (or a scenario script) fails and recovers links. After each event the controller recomputes routes and the system reports what was delivered, what was not, and why.

**Two baselines and one routing engine in two configurations, compared on identical scenarios:**

| Policy | What it is | Role |
|---|---|---|
| S0 Baseline | Dijkstra on latency. No capacity check, no priority. Overloaded links lose traffic proportionally. | The naive floor |
| S0-QoS Priority baseline (Must) | Same routes as S0. Each overloaded link serves classes in strict priority order. | **The thing to beat**: what QoS queueing gives with no rerouting |
| S1 Capacity-aware | Same engine as S2 with: arrival order, one path per flow, latency-only cost | Ablation: isolates the value of capacity awareness |
| S2 Improved (primary) | Flows allocated in priority order (critical first). Each flow is placed by repeated shortest-path search on the **residual-capacity graph**, split across at most m paths, with an optional congestion penalty on link cost. | The submission |

**Why this one.** It is a small mechanism (one loop, one residual-capacity ledger, one Dijkstra call) that gives hard capacity safety, strict class priority, flow splitting, and a natural explanation for every decision. It needs no k-shortest-path enumeration and no solver. S1 and S2 are the same code with different settings, so the ablation costs almost nothing.

**The claim we make.** S2 beats S0 on critical delivery by construction, because S0 has no priority, so that comparison is shown but is not the headline. The headline is S2 against **S0-QoS**: total delivery (`DR`), P1 delivery (`DR_P1`) and overloaded links. On critical delivery (`DR_P0`) we expect S2 to match S0-QoS when one path can carry all P0 traffic and to win only when P0 needs more than one path. This is checked at H8 on the demo network, and whatever the run shows is what we say.

**What it guarantees:** no failed link used, no capacity exceeded, a higher class never loses capacity to a lower class, and deterministic output. **What it does not guarantee:** the maximum possible delivered traffic. It is a greedy heuristic and can be suboptimal. A per-flow max-flow bound (section 5) reports the gap for every unserved flow, and an optional LP reference (section 8) measures the overall gap on small cases.

**Deliberately cut from the earlier idea list** (kept in the roadmap, section 14): scaling study across network sizes, WebSocket push, cascading-failure model, SRLG, vulnerability analyzer, what-if preview, repair prioritizer, Monte-Carlo robustness curve, natural-language box. They are good ideas, but each costs hours and none is needed for a complete, measurable demo.

---

## 2. Assumptions and scope

**Model assumptions**
- **Fluid, steady-state.** Flows are constant-rate demands. No packets, queues, protocol convergence delay, or time-varying traffic.
- **Centralized controller** with global knowledge of topology, link state and the traffic matrix (SDN-like). Not a distributed routing protocol.
- **Links are bidirectional and full duplex.** Each physical link is two directed arcs, each with the stated capacity. A link failure takes both arcs down. Utilization is per arc.
- **Integer inputs.** Capacity and rates in integer Mbps, latency in integer ms. Because every push is `min(remaining, bottleneck)`, S1 and S2 allocations stay integer. **S0 and S0-QoS deliveries are fractional** (a rate times a scale factor), so `delivered` and `unserved` are floats in the contract and equality checks on them use a tolerance of 1e-9.
- **Three priority classes:** P0 critical (auth, emergency), P1 academic, P2 best effort. The class list is configurable but ordered.
- **Flows are splittable** across up to `max_paths` paths (1 means unsplittable).
- **Node failure** is convenience sugar: it fails all incident links.

**Assumption register.** Each assumption has an owner who checks it at the stated hour.

| # | Assumption | Fact or inference | What would disprove it | Owner, hour | If wrong |
|---|---|---|---|---|---|
| A1 | After the primary uplink fails, the demo network still has at least two usable paths with spare capacity | Inference | The post-failure path check in section 9 fails | B, H4 | Add redundancy to the template at H4, while there is slack |
| A2 | S2 beats S0-QoS on total or P1 delivery on the demo network | Inference | Headline check at H8 shows a tie or a loss | Whole team, H8 | The three outcomes in section 12 |
| A3 | Recompute at 50 nodes and 200 flows takes under 1 second, including max-flow bounds | Testable | Median `compute_ms` on the first seed | A, H8 | Cut line in section 12: bounds become lazy, then `m = 2` |
| A4 | 30 seeds give a usable 95% interval for H1 | Testable | Interval width at H12 | D, H12 | Report the interval as it is |
| A5 | Judges accept per-class scale factors as a QoS model | Inference | Judge Q&A | D, README by H16 | Baseline-defence paragraph in the README; upstream-aware delivery if built |
| A6 | Four people with AI agents reach the H1.5 freeze and the H4 slice | Inference | A missed checkpoint | Everyone | Cut lines in section 12 |

**In scope (must have):** topology and traffic generation (from the UI as well as the CLI), link fail and recover, four policies (S0, S0-QoS, S1, S2), capacity accounting, metrics, decision log, reproducible scenarios, benchmark, interactive UI with side-by-side comparison, tests, README.

**Out of scope:** real router behaviour, packet-level queueing (S0-QoS models strict priority as per-link scale factors, section 5), scaling study beyond the demo network size, multi-domain routing, persistence/database, authentication, deployment infrastructure, machine learning.

**Claims we will and will not make.** Results show behaviour of this simulator on generated networks. They say nothing about production network performance.

---

## 3. Routing algorithm comparison

| # | Approach | Complexity | Impl. cost | Advantages | Limitations | 24 h fit |
|---|---|---|---|---|---|---|
| 1 | **Dijkstra shortest path (latency)**, recompute on failure | O(E log V) per flow | Very low | Simple, correct, explainable | Ignores capacity and priority; piles flows on the same links; silently overloads | **Use as baseline S0** |
| 2 | **Precomputed alternate / k-shortest paths** (Yen) | O(k·V·(E + V log V)) per pair | Medium | Gives a candidate list to display; fast failover | Candidates may all be congested; enumeration cost grows; k is a guess | Optional only |
| 3 | **Capacity-aware first-fit** (shortest path on residual graph, arrival order, one path) | O(F·E log V) | Low | Honors capacity; simple | Order-dependent; no priority; large flows fail whole | **S1 (ablation)** |
| 4 | **Congestion-aware link cost** (load-dependent weights, Fortz-Thorup style) | Same as 3 | Low (a weight function) | Spreads load before links saturate | Result depends on order; needs tuning of one parameter | **Feature flag in S2, kept only if ablation shows it helps** |
| 5 | **Priority-ordered greedy with flow-ordering policy** | Same as 3 | Low | Gives strict class priority; ordering policy is a testable choice | Greedy: early decisions can block later flows; not optimal | **Core of S2** |
| 6 | **Flow splitting by successive bottleneck pushes** | At most m Dijkstra calls per flow | Low | Uses fragmented capacity; no path enumeration | Splits cost paths; m caps complexity | **Core of S2** |
| 7 | **Multi-commodity flow LP** (edge or path formulation, HiGHS via scipy) | Polynomial (fractional), but F·E variables | Medium-high | Gives an upper bound and optimality gap | Needs flow decomposition to explain; slow at scale; integral (unsplittable) version is NP-hard | **Stretch: offline reference only** |
| 8 | **Rip-up and reroute / negotiated congestion** | Iterations × approach 5 | Medium | Can repair greedy mistakes | More moving parts, convergence not guaranteed | Roadmap |

**Recommendation: 1 + 3 + 4 + 5 + 6**, delivered as two configurations of one engine, with 7 as an optional check. Approaches 2 and 8 are not needed to solve the problem meaningfully. Explainability does not require candidate enumeration; section 10 shows how the decision log gets "alternatives considered" without Yen.

---

## 4. Mathematical problem definition

### Network
- Directed graph of arcs from physical links. Link `e = {u, v}` has capacity `c_e` (Mbps), latency `l_e` (ms), state `s_e ∈ {up, down}`. Arc `a` inherits `c_a = c_e`, `l_a = l_e`, and is **available** iff `s_e = up`.
- Effective capacity `ĉ_a = floor(ρ · c_a)`, with utilization cap `ρ ∈ (0, 1]` (default 1.0).
- Load `L_a = Σ x_{f,p}` over allocated paths containing `a`. Residual `r_a = ĉ_a − L_a`. Utilization `u_a = L_a / c_a`.

### Traffic
- Flow `f = (src_f, dst_f, b_f, π_f, name)` with demand `b_f` (Mbps) and class `π_f ∈ {P0, P1, P2}` (0 highest).
- Allocation: for each flow a set of `(path p, rate x_{f,p})` with `x ≥ 0`. Delivered `d_f = Σ_p x_{f,p}` (for S0, see delivery model in section 8).

### Hard constraints (S1, S2 always satisfy; S0 and S0-QoS do not satisfy constraint 4 and are measured on it)
1. Every used path consists only of available arcs.
2. Every path connects `src_f` to `dst_f` (simple path, no repeated node).
3. `Σ_p x_{f,p} ≤ b_f` (never deliver more than demanded).
4. For every arc: `L_a ≤ ĉ_a`.
5. A flow uses at most `max_paths` distinct paths.

### Objectives (ordered, lexicographic)
1. Maximize delivered P0 traffic.
2. Then maximize delivered P1.
3. Then maximize delivered P2.
4. Then minimize congestion (max utilization, or the sum of the convex congestion cost).
5. Then minimize path latency.

### Trade-offs
- **Delivered volume vs protection:** strict priority can reduce total delivered traffic compared with other orderings and gives P2 nothing when P0 saturates a bottleneck. This is intended, and it is reported (worked example below).
- **Congestion vs path cost:** spreading load increases latency. The parameter λ sets the exchange rate.
- **Churn vs simplicity:** every event is a full recompute from an empty ledger, so a flow can move even when its old path is still valid. Keeping old paths ("sticky" rerouting) was considered and cut: it carries state between events, makes sequential and simultaneous failures diverge, and is invisible in the demo. Churn is measured and reported instead.

### Edge-case semantics
- **Disconnected destination:** `src` and `dst` are in different components of the available graph. Cause `DISCONNECTED`. This is physical and not the algorithm's fault.
- **Insufficient capacity:** a path exists but residual capacity is exhausted. Cause `INSUFFICIENT_CAPACITY`.
- **Path limit:** residual paths exist but the flow already uses `max_paths`. Cause `PATH_LIMIT`.
- **Congestion loss (S0 only):** traffic lost on overloaded arcs. Cause `OVERLOAD_LOSS`.
- **Competing flows:** resolved by the ordering policy; ties by flow id for determinism.

### What the greedy guarantees and does not
**Guarantees:** hard constraints 1 to 5; **class isolation**: the allocation of class c is identical to what it would be if all lower classes did not exist (so a lower class can never reduce a higher class's delivery); determinism for a given input and config.

**Does not guarantee:** global optimality of delivered volume. Reasons: flows are placed one at a time; the order within a class matters; paths are chosen by cost, not by max-flow; `max_paths` limits splitting. So S2 can lose to S0 or S0-QoS on some inputs (for example when a baseline's scale factors happen to deliver more of a particular flow, or when a greedy push blocks capacity that max-flow would have used). We measure this and do not assume it away.

### Worked example (also used as unit tests)

Diamond: links AB (cap 10, lat 1), BD (10, 1), AC (10, 2), CD (10, 2), each direction. Flows: F1 P0 A→D 15 Mbps; F2 P2 A→D 10 Mbps.

| Case | S0 | S0-QoS | S2 (ρ = 1, m = 3) |
|---|---|---|---|
| Healthy | Both on A-B-D, load 25 vs cap 10, scale 0.4. F1 = 6, F2 = 4. P0 ratio 0.40, total 0.40. 2 overloaded arcs, excess 30. | Both on A-B-D. P0 takes the whole link: F1 = 10, F2 = 0. P0 0.667, total 0.40. Same 2 overloaded arcs. | F1: 10 on A-B-D, 5 on A-C-D, delivered 15. F2: 5 on A-C-D, 5 unserved `INSUFFICIENT_CAPACITY`. P0 1.00, P2 0.50, total 0.80. 0 overloaded arcs. |
| BD fails | Both on A-C-D, load 25 vs 10. F1 = 6, F2 = 4. P0 0.40, total 0.40. | Both on A-C-D. F1 = 10, F2 = 0. P0 0.667, total 0.40. | F1: 10 on A-C-D, 5 unserved. F2: 10 unserved. P0 0.667, total 0.40. 0 overloaded. |

The honest takeaway, and what the demo should say:
- **While a second path exists (row 1), S2 beats S0-QoS on both critical and total delivery** (1.00 vs 0.667, 0.80 vs 0.40), because it uses capacity that shortest-path routing leaves idle.
- **When only one path is left (row 2), S2 and S0-QoS deliver the same.** Rerouting cannot create capacity. The remaining difference is that S2 admits only what fits, so no link is overloaded.

Every number in this table is an exact integer. Fixtures must also include one case with a non-integer S0 delivery (for example a 7 Mbps flow scaled by 0.4) so the float contract is exercised from the first hour.

---

## 5. Recommended algorithm and pseudocode

### Cost function (S2, optional)
Congestion slope `s(u)` is the Fortz-Thorup piecewise-linear slope: 1 for `u < 1/3`, 3 for `u < 2/3`, 10 for `u < 0.9`, 70 for `u ≥ 0.9` (the remaining slopes apply only above 100%, which the hard cap forbids). Arc weight:

```
w_a(u) = l_a + λ · (s(u) − 1)         # λ = 0 gives pure latency
```
Default λ = mean link latency rounded to an integer; it is decided by experiment (section 5, knobs). Latency, λ and the slopes are all integers, so arc weights and path costs are integers and tie-breaking never depends on float rounding.

### Baseline S0

```
route_S0(topo, flows):
    G = arcs of links with state up
    for f in flows sorted by id:
        p = dijkstra(G, f.src, f.dst, weight=latency)   # ties: (cost, hops, node ids)
        alloc[f] = [(p, f.rate)]  if p exists
                   else []        with cause DISCONNECTED
    L[a] = sum of rates of flows whose path uses arc a
    # delivery model with no admission control:
    for f: scale_f = min over arcs a on p of min(1, c_a / L[a])
           d_f = f.rate * scale_f
    return alloc, d
```
Delivery model note: this is a single-pass approximation (it ignores that upstream loss frees downstream capacity). It is conservative and deterministic, and is documented as such.

### Priority baseline S0-QoS (Must)

Same routes and same offered load as S0. Only the delivery model changes: each arc serves classes in strict priority order.

```
route_S0_QoS(topo, flows):
    alloc = routes from route_S0                         # identical paths
    L[a][k] = offered load of class k on arc a
    for each arc a, for class k in 0, 1, 2:
        avail      = max(0, c_a − sum of L[a][j] for j < k)
        scale[a][k] = 1 if L[a][k] == 0 else min(1, avail / L[a][k])
    for f: d_f = f.rate * min over arcs a on p of scale[a][f.cls]
    return alloc, d
```
It is the same single-pass approximation as S0 and is built in the same block of work (about 15 lines on top of S0). It is the baseline every headline number is quoted against.

**Known bias, and the optional fix.** The single-pass model under-delivers for the baselines: traffic lost on an upstream link still counts as load downstream. That bias favours S2, so the README states it. If core is stable at H12, A adds an upstream-aware version behind a flag and the benchmark reports both:

```
deliver_upstream_aware(alloc, per_class):
    scale[a][k] = 1 for all arcs and classes
    repeat up to 50 rounds, or until no scale changes by more than 1e-9:
        for each flow f, walking its path from the source:
            arriving[f][a] = f.rate * product of scale[b][f.cls] for arcs b before a on the path
        L[a][k] = sum of arriving[f][a] over flows of class k on arc a
        recompute scale[a][k] from L exactly as in route_S0_QoS
    d_f = f.rate * product of scale[a][f.cls] over all arcs on the path
```
It has to iterate because two flows can cross the same links in opposite order, so there is no single pass that is correct. It is not on the path to any milestone.

### Improved S2 (same function with a config object)

```
Config: order ∈ {arrival, class_size_desc, class_size_asc}
        max_paths m, congestion λ, util_cap ρ

allocate(topo, flows, prev_alloc, cfg):                     # prev_alloc is only copied into the log
    ledger = Ledger(available arcs, cap = floor(ρ * c))     # empty on every event; tracks residual and per-class load
    comp   = connected components of available graph
    for f in order(flows, cfg.order):                       # class first, then policy within class
        rec = DecisionRecord(f)
        if comp[f.src] != comp[f.dst]:
            result(f) = unserved, cause DISCONNECTED; log; continue
        remaining, paths = f.rate, {}
        rec.previous = prev_alloc[f] if f in prev_alloc else []     # for the log only, never reused

        # 1. Place the flow on the residual graph
        ref = dijkstra(available graph, latency)            # reference path, ignores capacity (for log)
        while remaining > 0 and len(paths) < cfg.max_paths:
            R = arcs with ledger.residual > 0
            p = dijkstra(R, f.src, f.dst, weight=w_a(ledger.util(a)))
            if p is None: break
            x = min(remaining, ledger.bottleneck(p))
            ledger.reserve(p, x); paths[p] += x; remaining -= x
            rec.attempt(p, cost(p), bottleneck(p), x)

        # 2. Unserved remainder
        if remaining > 0:
            cause = PATH_LIMIT if residual path still exists else INSUFFICIENT_CAPACITY
            if cause == INSUFFICIENT_CAPACITY:               # no cut exists under PATH_LIMIT
                rec.cut = arcs leaving the set reachable from src in R   # saturated or failed arcs
                rec.cut_load_by_class = ledger.class_breakdown(rec.cut)  # includes f's own load
            pre = ledger residuals with f's own reservations added back
            rec.maxflow_bound = min(f.rate, maxflow(pre, f.src, f.dst))  # networkx, unserved flows only
            rec.greedy_gap    = rec.maxflow_bound − delivered            # > 0: the greedy left capacity unused
        rec.reference_path_note(ref, paths)                  # why the latency-shortest path was not (fully) used
        alloc[f] = paths; log.append(rec)
    return alloc, log
```

**Why it terminates and is cheap:** each push either satisfies the flow or saturates at least one arc, and at most m pushes happen per flow, so at most m + 1 Dijkstra calls per flow. Total O(F · m · E log V).

**Known weakness and how it is exposed.** The loop pushes along shortest paths and has no reverse arcs, so it is not a max-flow algorithm: an early push can block capacity a later push needed, and `max_paths` limits it further. For every unserved flow the record therefore carries `maxflow_bound`, the most that flow could have received given what higher-priority flows already hold. `greedy_gap = 0` means the shortfall is real and the cut explains it. `greedy_gap > 0` means the greedy (or the path limit) is to blame, and the explanation says so instead of presenting the cut as a physical limit. The sum of `greedy_gap` over P0 flows is a reported metric.

**Invariants maintained:** ledger residual is never negative; sum of reservations on an arc equals its load; every reservation is on available arcs; delivered never exceeds demand.

### Event handling

```
on_event(event):                     # fail(links|node) / recover(links)
    topo.apply(event)                # atomic: simultaneous failures are one event
    affected = {f : some path of f in current_alloc uses a now-down arc}
    new_alloc, log = policy.route(topo, flows, current_alloc, cfg)   # full recompute, fail or recover
    snapshot = metrics(topo, flows, new_alloc, affected, previous=current_alloc)
    check_invariants(snapshot)       # always on in tests, optional in demo
    current_alloc = new_alloc
    return snapshot
```

- **Multiple failures:** simultaneous (one event with several links) or sequential (several events). Both supported; sequential shows the progression, simultaneous shows the worst case. Because every event recomputes from an empty ledger, the two give the same final state; only the intermediate snapshots differ.
- **Unreroutable flows:** reported with cause and cut links, never silently dropped.
- **Recovery:** the same full recompute, so flows return to shortest/least-cost routes. The churn this causes is itself a reported metric.

### Why full priority-ordered recompute and not incremental
Rerouting only the affected flows could let unaffected P2 flows hold capacity that an affected P0 flow needs. Full recompute in priority order avoids that. The cost is churn of lower-class flows, which is intentional and measured. Because routing is deterministic, flows ordered before the first affected flow get the same paths as before, so churn after a failure is limited to that flow and those after it.

### Design knobs decided by experiment (room for independent decisions)
Do not hard-code these. Run ablations (section 9) and pick by data.

| Knob | Options | Experiment |
|---|---|---|
| Ordering within class | arrival, size desc, size asc | Compare total delivered and number of served flows |
| `max_paths` m | 1, 2, 3, 4 | Delivered vs compute time vs path fragmentation |
| λ | 0, 0.5, 1, 2 × mean latency, each rounded to an integer | Max utilization vs latency stretch |
| ρ (utilization cap) | 1.0, 0.9 | Headroom vs delivered |

If λ > 0 shows no measurable benefit over λ = 0, **remove it** and report that. A smaller algorithm is preferred.

---

## 6. Architecture and technology stack

```
 React UI (Cytoscape graph, KPI, flow table, decision log, compare)
        │  REST/JSON
 FastAPI (thin; holds in-memory sessions)
        │
 ┌──────┴─────────────────────────────────────────┐
 │ core library (pure Python, no web imports)     │
 │  model/    topology, flows, allocation types   │
 │  gen/      topology + traffic generators       │
 │  routing/  policy interface, S0, allocator     │
 │  sim/      simulator, events, scenarios        │
 │  metrics/  formulas, invariant checker         │
 │  explain/  decision records                    │
 └────────────────────────────────────────────────┘
        │
 CLI: run scenario, compare policies, benchmark → CSV/JSON
```

**Rule:** the core library has no dependency on FastAPI or the frontend. It is testable and benchmarkable from the command line, which is how we validate correctness independently of the UI.

| Choice | Justification |
|---|---|
| Python 3.11+, pydantic v2 | Fast to write, typed models give the shared contract, JSON export is free |
| networkx | Connectivity, Dijkstra with callable weights, and `maximum_flow_value` for the per-flow bound. Wrapped in one `pathfinder.py` |
| FastAPI | Auto OpenAPI contract that the frontend can code against from hour 1 |
| pytest + hypothesis | Property tests for invariants over random scenarios, cheap to write |
| React + Vite + TypeScript | Standard, fast, typed API client from the OpenAPI schema |
| Cytoscape.js | Ready graph rendering and styling; avoids custom canvas work |
| Recharts | Benchmark charts |
| REST only | Each event recompute is a request/response. WebSocket adds failure modes for no demo benefit |
| scipy (HiGHS) | Only for the optional LP reference; no extra install |

Not used: microservices, database, containers, ML, external services. Everything runs locally from two commands.

### Data flow
1. Scenario (topology spec + traffic spec + events + seed) is loaded or generated by `gen/`.
2. `Simulation` holds topology state and the current allocation.
3. Each event calls `policy.route(...)`, which returns an `Allocation` and a `DecisionLog`.
4. `metrics/` computes a `Snapshot` from the state alone (not from algorithm internals).
5. API serializes snapshots. UI renders them. CLI writes them to files.

---

## 7. Data models and component interfaces

These are **frozen at hour 1.5** and live in `core/model/types.py` plus JSON fixtures in `fixtures/`. The freeze is valid only if every type named below is written out as a pydantic model and a fixture of each validates, including one S0 snapshot with a non-integer `delivered` and the decision-record example from section 10.

```python
class Node(BaseModel):  id: str; type: str; name: str
class Link(BaseModel):  id: str; u: str; v: str; capacity: int; latency: int; status: Literal["up","down"]
class Topology(BaseModel): nodes: list[Node]; links: list[Link]

class Flow(BaseModel):  id: str; src: str; dst: str; rate: int; cls: int      # 0 = P0
                        service: str = ""

class PathAlloc(BaseModel): arcs: list[str]; rate: int        # arc id = "L7:u>v"
class FlowResult(BaseModel):
    flow_id: str; paths: list[PathAlloc]
    delivered: float; unserved: float       # fractional under S0 and S0-QoS
    cause: Literal["NONE","DISCONNECTED","INSUFFICIENT_CAPACITY","PATH_LIMIT","OVERLOAD_LOSS"]
class Allocation(BaseModel): results: dict[str, FlowResult]; arc_load: dict[str, int]   # offered load

class PolicyConfig(BaseModel):
    order: Literal["arrival","class_size_desc","class_size_asc"] = "class_size_desc"
    max_paths: int = 3; congestion_lambda: int = 0; util_cap: float = 1.0

class Event(BaseModel):
    step: int; kind: Literal["fail","recover"]; links: list[str] = []; node: str | None = None

class Attempt(BaseModel):
    iter: int; arcs: list[str]; cost: int; latency: int; bottleneck: int; pushed: int
class CutArc(BaseModel):
    arc: str; state: Literal["saturated","down"]; load_by_class: dict[int, int]
class DecisionRecord(BaseModel):
    flow_id: str; cls: int; demand: int; step: int
    failed_links: list[str]; previous: list[PathAlloc]
    reference_path: list[str]; reference_status: str
    attempts: list[Attempt]
    delivered: float; unserved: float; cause: str
    cut: list[CutArc]                       # empty unless cause is INSUFFICIENT_CAPACITY
    maxflow_bound: int | None; greedy_gap: float | None     # set for unserved flows under S1/S2
    explanation: str                        # the one-line text from section 10
    # S0 and S0-QoS fill flow_id, cls, demand, step, reference_path, delivered, unserved, cause, explanation

class Metrics(BaseModel):
    dr: float; dr_by_class: dict[int, float]; dr_reach: float
    unserved_by_cause: dict[str, float]
    overloaded_arcs: int; overload_excess: int
    max_util: float; mean_util: float; arcs_above_90: int
    link_util: dict[str, float]             # per physical link, see rule below
    latency_stretch: float; recovery_ratio: float | None
    churn_flows: int; churn_rate: int
    p0_greedy_gap: float; compute_ms: float
```

**Link display rule.** Utilization is per arc, but the UI draws one edge per physical link. `link_util[link] = max` of its two arc utilizations, computed by the backend. The UI colours the edge from this value and never derives it itself. Values above 1.0 (S0, S0-QoS) are drawn in the overload colour.

```python
class RoutingPolicy(Protocol):
    name: str
    def route(self, topo: Topology, flows: list[Flow],
              prev: Allocation | None, cfg: PolicyConfig) -> tuple[Allocation, list[DecisionRecord]]: ...
    # Must be pure and deterministic: no globals, no clocks, no unseeded randomness.
    # `prev` is copied into DecisionRecord.previous for the log. It must not influence the allocation.

class Ledger:               # capacity accounting, owned by B
    def residual(self, arc) -> int
    def bottleneck(self, path) -> int
    def reserve(self, path, rate) -> None     # raises if it would exceed capacity
    def release(self, path, rate) -> None
    def class_breakdown(self, arcs) -> dict[int, int]

class Simulation:
    def __init__(self, scenario, policy, cfg)
    def apply(self, event) -> Snapshot        # event: fail/recover links or node
    def reset(self) -> Snapshot
```

```python
class Scenario(BaseModel):
    id: str; seed: int
    topology: TopologySpec          # {template: "campus"} | {generator: "campus", buildings: 12, redundancy: 0.5, seed: ...}
    traffic:  TrafficSpec           # explicit list | {generator, n_flows, load_factor, class_mix, seed}
    events:   list[Event]           # [{step: 1, kind: "fail", links: ["L3","L7"]}, ...]
    config:   PolicyConfig

class Snapshot(BaseModel):
    step: int; link_state: dict[str, str]; allocation: Allocation
    metrics: Metrics; affected_flows: list[str]; decisions: list[DecisionRecord]
```

### REST API (contract; mocks served from day one)

| Method and path | Purpose |
|---|---|
| `GET /scenarios` | List built-in scenarios |
| `POST /runs` `{scenario_id or scenario, policy, config}` | Create a session and return the step-0 snapshot. Passing a `scenario` with a generator spec is how the UI's "Generate network" control works |
| `POST /runs/{id}/events` `{kind, links}` | Apply a failure or recovery and return the new snapshot |
| `POST /runs/{id}/reset` | Return to step 0 with the same seed |
| `POST /compare` `{scenario, policies[]}` | Run all policies on identical state and return a table plus per-policy snapshots |
| `GET /runs/{id}/flows/{flow_id}/decision` | Decision record for one flow |

Reproducibility rules: all randomness through `random.Random(seed)` passed explicitly; sort by id wherever iteration order could matter; Dijkstra tie-break `(cost, hops, node ids)`; never depend on dict or set ordering.

---

## 8. Optimization objectives and metrics

Let `D = Σ b_f`, `d_f` delivered, `C_k` flows of class k.

| Metric | Formula |
|---|---|
| Delivery ratio | `DR = Σ d_f / Σ b_f` |
| Class delivery ratio | `DR_k = Σ_{f∈C_k} d_f / Σ_{f∈C_k} b_f` |
| **Headline set** | `DR`, `DR_P1` and overload violations for **S2 against S0-QoS**. `DR_P0` is shown for all policies; against S0-QoS it is a win only where P0 needs more than one path |
| P0 greedy gap | `Σ_{f∈C_0} greedy_gap_f` (section 5). Zero means no critical traffic was lost to the heuristic |
| Reachable-only delivery | `DR_reach = Σ d_f / Σ_{f reachable} b_f` (excludes `DISCONNECTED`) |
| Unserved by cause | `Σ (b_f − d_f)` grouped by cause |
| Utilization | `u_a = L_a / c_a` (S0 and S0-QoS use offered load, so it can exceed 1). Per-link display value is the max of the two arcs |
| Overload violations | count of arcs with `L_a > c_a`; excess `Σ max(0, L_a − c_a)` |
| Max / mean utilization, links above 90% | over available arcs |
| Latency stretch | `Σ d_f · lat_f / Σ d_f · lat0_f`, where `lat_f` is the rate-weighted path latency of f and `lat0_f` the shortest-path latency in the healthy topology |
| Affected flows | flows with a path through a newly failed link (computed before rerouting) |
| Recovery ratio | `Σ_{f∈A} d_f(after) / Σ_{f∈A} d_f(before)`; also the count of affected flows with `d_f(after) ≥ d_f(before)` |
| Churn | flows whose path set changed; rate moved `Σ x` on changed paths |
| Compute time | wall-clock of `policy.route` (median of repeated runs, never part of correctness checks) |
| Weighted delivery (secondary) | `Σ w_k · DR_k` with weights stated in the report; not a headline because weights are arbitrary |

Metrics are computed from `(topology, flows, allocation)` alone so they cannot disagree with the simulated state.

**Fair baseline (Must):** S0-QoS serves classes strictly by priority at each overloaded arc (per-arc, per-class scale factors, section 5). It answers the judge question "real networks have QoS queues, so is routing even needed?". Every headline comparison is against it. Report the scenarios where S2 beats it and the scenarios where it ties.

**Optional LP reference (Could):** path-based or edge-based multi-commodity flow solved lexicographically with scipy HiGHS on networks of 20 to 30 nodes. Reports `gap = (LP_delivered − S2_delivered) / LP_delivered` per class. Because it ignores `max_paths` unless paths are enumerated, label it "fractional upper bound", not "optimum".

---

## 9. Testing and benchmark scenarios

### Invariants (checked by `check_invariants`, run on every snapshot in tests)

| # | Invariant |
|---|---|
| I1 | No allocated path contains a down arc |
| I2 | Every path is a simple path from `src` to `dst` |
| I3 | `delivered ≤ demand`, and `delivered + unserved = demand` (tolerance 1e-9, since S0 and S0-QoS deliveries are floats) |
| I4 | For S1 and S2: `L_a ≤ ĉ_a` on every arc |
| I5 | Ledger reserve and release are symmetric; after releasing all allocations, every residual equals capacity |
| I6 | `arc_load` equals the sum of path rates through the arc |
| I7 | Every unserved flow has a cause. `DISCONNECTED` is reported only if the components really differ. `INSUFFICIENT_CAPACITY` is reported only if a path exists in the available graph |
| I8 | Same scenario, config and seed give a byte-identical snapshot sequence after masking the wall-clock field `metrics.compute_ms` |
| I9 | Metrics recomputed from the snapshot's allocation equal the reported metrics |
| I10 | Class isolation: removing all lower-class flows does not change a class's allocation (S2) |
| I11 | For every unserved S1/S2 flow: `0 ≤ greedy_gap`, and `cut` is non-empty only when the cause is `INSUFFICIENT_CAPACITY` |

### Unit and property tests
- Pathfinder: ties, parallel links, down links, no path.
- Ledger: reserve beyond capacity raises; release restores.
- Diamond examples from section 4 (exact expected numbers).
- Diamond S0-QoS column, and one fixture with a non-integer S0 delivery.
- A blocking example where shortest-path pushes deliver less than max-flow: assert `greedy_gap > 0` is reported.
- Hypothesis: random topologies and flows from seeds, assert I1 to I11.
- Metrics: hand-computed small cases.

### Scenario fixtures (each is a JSON file under `fixtures/` with assertions)

| # | Scenario | Setup | Expected qualitative result (verified by running, not assumed) |
|---|---|---|---|
| 1 | Normal operation | Campus template, load factor about 0.5 | All policies deliver nearly everything; S2 not worse than S0-QoS within tolerance; no overloads in S2 |
| 2 | Single critical-link failure | Fail the primary uplink | S0 and S0-QoS pile flows onto the backup and overload it; S2 splits across remaining paths and delivers more in total than S0-QoS |
| 3 | Multiple simultaneous failures | Fail 3 links in one event, then the same 3 sequentially | Identical final snapshot (asserted, apart from step number and `compute_ms`); the sequential run shows the progression |
| 4 | Congestion on alternatives | Two alternate routes, one nearly full | S2 with λ > 0 avoids the nearly full route; S1 does not. Tests whether congestion cost earns its place |
| 5 | Insufficient capacity | Demand exceeds min-cut | Unserved reported with `INSUFFICIENT_CAPACITY` and cut links; P2 loses first |
| 6 | Disconnected destination | Isolate a hostel | `DISCONNECTED` reported; `DR_reach` unaffected by the cut; S2 not blamed |
| 7 | Critical vs ordinary competing | Diamond example | Exact numbers from section 4 for S0, S0-QoS and S2 |
| 8 | Link recovery | Fail then recover | Recompute restores the step-0 allocation exactly (asserted); churn reported |

### Demo-network path check (B, at H4)
The story in scenario 2 needs somewhere for traffic to go after the failure. A test asserts, on the campus template **with the primary uplink already failed**, that every building still has at least two node-disjoint paths to the core, and that their combined capacity exceeds the P0 plus P1 demand of that building. Checking before the failure is not enough: two paths before means one path after, which is the tie case in the diamond's second row. The campus generator runs the same check on its designated uplink and retries with the next seed (at most 20 times, then raises).

### Experimental method
- **Identical conditions:** a scenario is generated once from `(spec, seed)`; every policy runs on a deep copy of the same topology, flows and events.
- **Network size:** one size only, the campus generator at about 50 nodes and 200 flows. There is no scaling study (see below).
- **Seeds:** 30 seeds of the campus generator, each with a random failure set; report mean, median and 95% bootstrap confidence interval. Fixed fixtures (1 to 8) are single deterministic runs.
- **Policies:** S0, S0-QoS, S1, S2 on every seed.
- **Ablations:** S2 with each knob from section 5 toggled one at a time, on the same 30 seeds.
- **Offered load factor:** scale all demands by a factor λ_L ∈ {0.5, 0.75, 1.0, 1.25, 1.5, 2.0}, report DR, DR_P1 and DR_P0 vs λ_L for each policy.
- **Time the first seed before launching the rest.** If the full matrix would exceed 30 minutes, cut ablations to `max_paths` and λ only.

### What counts as a meaningful improvement (stated before running, reported either way)
- **H1 (headline):** In stress scenarios (2, 3, 4, 5), mean `DR` of S2 exceeds **S0-QoS** by at least 10 percentage points, with the 95% interval above zero.
- **H1b:** In the same scenarios, S2 `DR_P0` is not below S0-QoS `DR_P0` by more than 1 percentage point. A larger S2 lead is reported where it occurs but is not required.
- **H2:** In uncongested scenarios (1, 8), S2 `DR` and `DR_P0` are within 1 percentage point of S0-QoS.
- **H3:** S2 has zero overload violations by construction; S0 and S0-QoS have some in stress scenarios.
- **H4:** The recompute time for the 50-node, 200-flow case stays within an interactive budget (target under 1 second; measured, not assumed).
- **H5:** P0 greedy gap is zero on at least 95% of benchmark runs. Runs where it is not are listed.
- The S2 against S0 comparison on `DR_P0` is reported for context only. It is not a hypothesis, because S0 has no priority and loses by construction.
- If a hypothesis fails, report it and the reason. The README includes a "limitations" section listing cases where S2 ties or loses to S0-QoS.

### Scaling study: cut
The earlier plan crossed five network sizes with four flow counts, three generators and ten seeds. It is removed. It consumed hours from three members, a campus network is not 500 nodes, and nothing in the problem statement asks for it. H4 keeps a single timing measurement at demo size. The study is on the roadmap (section 14).

---

## 10. Explainability and UI design

### Decision log (per flow, per event)

```json
{
  "flow_id": "F12", "cls": 0, "demand": 15, "step": 2,
  "failed_links": ["L7"],
  "previous": [{"arcs": ["L2:A>B", "L7:B>D"], "rate": 10}],
  "reference_path": ["L2:A>B", "L7:B>D"],
  "reference_status": "INVALID: L7 down",
  "attempts": [
    {"iter": 1, "arcs": ["L5:A>C", "L6:C>D"], "cost": 4, "latency": 4, "bottleneck": 10, "pushed": 10}
  ],
  "delivered": 10.0, "unserved": 5.0, "cause": "INSUFFICIENT_CAPACITY",
  "cut": [
    {"arc": "L5:A>C", "state": "saturated", "load_by_class": {"0": 10}},
    {"arc": "L7:B>D", "state": "down", "load_by_class": {}}
  ],
  "maxflow_bound": 10, "greedy_gap": 0.0,
  "explanation": "F12 (P0, 15 Mbps): path A-B-D invalid (L7 down). Moved 10 Mbps to A-C-D (latency 4 ms). 5 Mbps unserved: cut L5 saturated by P0 (10 Mbps)."
}
```

**How "alternatives considered" works without enumerating paths:** the log records (a) the reference path (shortest ignoring capacity) and why it was not used (down link, or the arc where residual ran out), (b) each residual-graph attempt with its cost and bottleneck, and (c) the **cut**: the set of saturated or failed arcs that separate source from destination in the residual graph. Its `load_by_class` shows who is holding the capacity (for example "saturated by P0 flows, 10 Mbps"), and that load can include the flow's own traffic.

**The cut is only presented as the reason when `greedy_gap = 0`.** In that case the flow received everything it could, given higher-priority allocations, and the cut is a checkable answer to "why was traffic left unserved". When `greedy_gap > 0` the template says instead: `N Mbps unserved, of which G Mbps could have been routed (heuristic or path limit)`. Under `PATH_LIMIT` there is no cut and none is shown.

The JSON above has exactly the fields of the `DecisionRecord` model in section 7. It is saved as a fixture and must validate against that model before the contract is frozen at H1.5.

**One-line UI explanation** is generated from the record by a fixed template, never by free text:
`F12 (P0, 15 Mbps): path A-B-D invalid (L7 down). Moved 10 Mbps to A-C-D (latency 4 ms). 5 Mbps unserved: cut L5 saturated by P0 (10 Mbps).`

**Use for debugging:** records are JSON, deterministic, diffable between two runs, and the invariant checker cross-checks them (for instance, every `pushed` amount equals what the ledger shows). A failing scenario can be replayed from its seed and its log read top to bottom.

### Minimum UI for a convincing demo (Must)
1. Topology graph: link color from `metrics.link_util` (green to red, overload colour above 1.0), failed links red dashed, thickness by capacity, node labels for key services.
2. Click a link to fail it; click again to recover.
3. **Side-by-side view:** the same network under a baseline and S2 simultaneously, same event applied to both. The baseline panel has a two-way selector, **S0-QoS (default) or S0**.
4. KPI strip per side: DR, DR_P0, DR_P1, overloaded links, unserved by cause.
5. Flow table: class color, demand, delivered, status. Click a flow to highlight its routes on the graph and open its decision record with the one-line explanation.
6. Scenario selector, seed display, reset button.
7. **Generate network:** a small form (number of buildings, redundancy, seed) that posts a generator scenario to `POST /runs` and loads the result in both panels. This is what satisfies "allow users to create or generate a network topology" on screen.

### Optional polish (Should / Could)
Benchmark charts (Recharts), event timeline with scrub, before/after path diff overlay, dark theme, export report. Hover what-if preview is on the roadmap, not here.

---

## 11. Four-member responsibility matrix

| | Owns | Delivers | Depends on | Does not own |
|---|---|---|---|---|
| **A: Routing** | `routing/` pathfinder, S0, S0-QoS, allocator with config, decision records (including the `DecisionRecord` type at H0 to 1.5), residual-cut and max-flow bound; ablation tuning; optional LP reference | Policies behind the `RoutingPolicy` interface, diamond unit tests, per-flow decision log | `types.py`, `Ledger` (from B at H1.5) | UI, API |
| **B: Simulation, model and metrics** | `model/`, `gen/`, `sim/`, **`metrics/` and the invariant checker**, ledger, campus template, one campus generator, traffic generator, event format, failure/recovery incl. node failure, seeding and determinism, demo-network tuning | Pydantic types, `Ledger`, `Simulation`, `Metrics`, `check_invariants`, generator, 8 scenario fixtures (inputs and their assertions) | Nothing at start; A consumes B's types first | Algorithms, API |
| **C: Frontend** | Entire React app: graph, link click, side-by-side with baseline selector, KPI strip, flow table, decision panel, generate-network form, charts | Working UI against mock data from H1.5, then live API | OpenAPI contract and fixtures (D, B) | Backend logic |
| **D: Integration and QA** | FastAPI and sessions, scenario loader, compare endpoint, hypothesis tests (using B's checker), benchmark CLI and results, README, demo script | API serving mocks by H1.5, then real policies; benchmark tables; README | Types and metrics (B), policies (A) | Algorithm design, metrics formulas, UI |

**Why metrics moved to B.** D previously owned every integrating piece (metrics, invariants, API, tests, benchmark, README, demo script) and was on the critical path of every milestone, while B had slack from H12. Metrics are pure functions of B's own types, so B writes them. If D is still behind at any checkpoint, B takes the benchmark run as well.

**Shared contract, frozen at H1.5:** `types.py` with **every** model in section 7 written out (including `DecisionRecord`, `Metrics`, `PolicyConfig`, `Event`), JSON fixtures (one snapshot per policy for the diamond and the campus, plus one S0 snapshot with a non-integer `delivered`), OpenAPI. Changes after H1.5 require all four to agree in chat and update the fixtures first.

### AI-assisted development (all four members)

Every member builds with an AI coding agent (OpenCode, Claude Code, Antigravity or similar; each person picks their own). Four agents writing into one repo fail in predictable ways, so these rules apply to everyone:

- **One shared instruction file.** At H0 to 1.5, B writes `AGENTS.md` at the repo root: stack, folder ownership, the determinism rules from section 7, the test command, and "never edit `core/model/types.py` or `fixtures/`". Each tool's own instruction file (for example `CLAUDE.md`) points to it, so all agents work from the same rules.
- **Agents stay inside their owner's folder.** A's agent edits `routing/` and `explain/`, B's edits `model/`, `gen/`, `sim/`, `metrics/`, C's edits the frontend, D's edits the API, tests and CLI. A change needed in someone else's folder is requested from that person, not made by the agent.
- **The contract is edited by humans only.** `types.py`, the fixtures and the OpenAPI schema change only by the section 11 rule (all four agree, fixtures first). An agent that "fixes" a type to make its own code pass breaks the other three.
- **Prompt with the plan, not from memory.** Give the agent the relevant section of this file plus `types.py`: section 5 pseudocode for the allocator, section 8 formulas for metrics, section 10 for the UI.
- **Expected numbers are worked by hand.** The diamond table in section 4 and the hand-computed metric cases are written by a person before the code exists. An agent must never generate both the implementation and the expected values it is tested against.
- **Tests and invariants are the acceptance gate.** Agent output is merged only when the owner's tests and `check_invariants` pass. A failing test is fixed in the code; the agent is not allowed to weaken or delete the assertion.
- **The owner must be able to explain the code.** Judges ask how the algorithm works. A in particular reads and can walk through every line of the allocator.
- **Small commits, each on the owner's branch, merged at every checkpoint.** Commit after each working step so a bad agent edit is one `git revert` away.

AI speeds up writing code. It does not speed up integration, tuning the demo network or rehearsal, so the hour plan and cut lines in section 12 stay as they are; time saved goes into the buffer.

**Everyone writes tests for their own module** (not left to D). **Everyone rehearses the demo** in the last block; nobody is presentation-only. C also owns the demo laptop setup; D owns the recorded fallback.

**Checkpoints (full-team integration, 10 minutes each):** H4 vertical slice, H8 improved routing, H12 demo scenario end to end, H16 feature freeze, H20 rehearsal.

---

## 12. Hour-by-hour execution plan

| Hours | A: Routing | B: Simulation, model, metrics | C: Frontend | D: Integration/QA | Exit criteria |
|---|---|---|---|---|---|
| 0 to 1.5 | Work diamond example on paper (all three columns); sketch allocator; write `DecisionRecord` with B | `types.py` with every section 7 model, `Ledger`, repo skeleton with git and `AGENTS.md` | Vite + Cytoscape scaffold rendering a fixture | FastAPI skeleton serving mocked snapshots; pytest set up | Contract frozen with no undefined type; a non-integer S0 fixture and the section 10 decision-record example validate; C renders a mocked snapshot fetched from the API |
| 1.5 to 4 | Pathfinder; S0 and S0-QoS with delivery models; diamond tests | Campus template; traffic generator; fail/recover events; minimal `Simulation.apply`; basic metrics (DR, overloads, `link_util`); post-failure path check on the template | Click-to-fail calls API; utilization coloring; flow table | Scenario loader; sessions; wire real S0 and S0-QoS through API | **M1 (H4): vertical slice**: click a link, see both baselines reroute and metrics in the UI |
| 4 to 8 | Allocator (S1/S2 via config); decision records with max-flow bound | Full metrics; invariant checker; node failure; recovery; seeds; determinism check; scenario fixtures 1 to 7 with assertions | Side-by-side view with baseline selector; KPI strip | Hypothesis tests I1 to I10 on B's checker; `/compare` endpoint; benchmark CLI skeleton | **M2 (H8): S2 passes all invariants on all fixtures, and the headline check is run** (below) |
| 8 to 12 | Residual-cut explanations; max-flow bound and `greedy_gap` (I11); ablation runs; tune knobs by data | **H8 to H10: tune the demo network against S0-QoS and S2.** Then the campus generator; load-factor scaling; fixture 8 | Flow inspector with route highlight and decision text; generate-network form | Benchmark CLI writing CSV; time one seed and size the matrix | **M3 (H12): demo scenario runs baseline and S2 in the UI with explanation; a generated network loads** |
| 12 to 16 | Fix algorithm issues found by benchmark; keep or drop λ based on ablation | Determinism and edge-case audit; take over the benchmark run or results tables if D is behind | Benchmark charts; reset and seed UI; visual polish | Run full benchmark; generate tables; evaluate H1 to H5; draft results | **H16: feature freeze.** Results exist, hypotheses evaluated |
| 16 to 20 | Bug fixes only; algorithm doc | Bug fixes only; model doc | Bug fixes; demo-mode layout | Edge-case sweep; README with setup, model, limitations, architecture diagram | All tests green; README complete |
| 20 to 22 | Rehearse; backup run | Rehearse | Rehearse; test on demo machine | Record fallback video and save a fallback run JSON | Two timed full rehearsals |
| 22 to 24 | Buffer | Buffer | Buffer | Final tag; submit | Done; no new features |

**Headline check at H8 (10 minutes, whole team).** Run S0, S0-QoS and S2 on the campus template with the primary uplink failed, and read `DR`, `DR_P1` and `DR_P0`. There are three outcomes:
- S2 beats S0-QoS on `DR` or `DR_P1`: proceed; that is the headline.
- S2 only ties S0-QoS: B's H8 to H10 tuning adds a second, longer path with spare capacity so that splitting has something to use. If it still ties after tuning, the pitch becomes "same critical delivery as QoS, with zero overloaded links and an explanation for every drop", and the demo says so.
- S2 loses to S0-QoS: this is an algorithm bug or a greedy shortfall. A fixes it before any explanation or ablation work.

**Benchmark reruns.** Any algorithm fix after the benchmark has run invalidates its tables. The final benchmark is rerun once at H16 on the frozen code, and only numbers from that run are spoken in the demo.

**Rest:** stagger one 90-minute nap per person between H10 and H18, with the other three working. Never all four idle or all four tired at once. Do not start rehearsal after H20 with unresolved invariant failures.

### Cut lines

| When | If behind | Then |
|---|---|---|
| H4 | D has not wired S0 through the API | B pairs with D until M1 passes; campus template tuning waits |
| H8 | S2 does not pass invariants | Drop the congestion cost (`λ = 0`) and set `m = 2`, but **keep splitting**: splitting is what separates S2 from S0-QoS. Drop to `m = 1` only as a last resort, and then expect a tie with S0-QoS on delivery |
| H8 | Frontend side-by-side not ready | Show two stacked panels with the same graph component; or toggle between policies |
| H12 | Flow inspector not ready | Show the decision record as formatted text in a side panel |
| H8 | Recompute takes 1 second or more (A3) | Stop computing max-flow bounds at route time. The decision endpoint computes one on request by replaying the allocation up to that flow, so the bound still uses the ledger as it was when the flow was placed. The benchmark computes them offline. If still slow, set `m = 2` |
| H12 | Generate-network form not ready | Ship a seed field only: same generator, default size |
| H12 | Benchmark behind | Run 10 seeds instead of 30, all four policies, no ablations |
| H16 | Always | **Freeze features.** Only fixes and docs after this |
| Only if core is stable at H12 | Add | Upstream-aware baseline delivery (section 5), LP reference, timeline scrubber, hypothesis-test polish. None of these enters the frozen contract |
| Never | Add | Scaling study, extra generators, cascades, SRLG, NL box, WebSocket, database |
| Never | Cut | S0-QoS. Without it the headline has no fair baseline |

---

## 13. Risks, edge cases, and fallback strategies

### Edge cases to handle and test
`src == dst` (treated as delivered with no network use); zero-rate flow; two flows with the same pair; parallel links between the same nodes; link with capacity 0; flow larger than any single bottleneck (needs splitting); `max_paths` reached with residual left (`PATH_LIMIT`); node failure isolating hosts; failure of an already-failed link (idempotent); recovery of an already-up link (no-op); all P0 flows saturating a bottleneck (P2 starved by design); ties in cost (deterministic tie-break); path containing the same node twice (never selected).

### Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Greedy is order-sensitive and not optimal | Weak claim; a feasible P0 flow left unserved | State this; per-flow `maxflow_bound` and `greedy_gap` in every record; H5 on the P0 gap; do not claim optimality |
| Congestion penalty does not help | Wasted effort | It is a flag; drop it if ablation shows no benefit |
| Baseline seen as a strawman | Kills the Optimization score | S0-QoS is a Must built at H1.5 to H4 and is the default baseline in the UI; all hypotheses are against it; ties are reported |
| S2 only ties S0-QoS on the demo network | No visible win | Headline check at H8, tuning at H8 to H10 once both policies exist, fallback pitch defined in section 12 |
| D overloaded as sole integrator | Every milestone slips | Metrics and invariant checker moved to B; B backs up D from H12; H4 cut line |
| Benchmark matrix too slow | No results by H16 | One network size; time one seed first; cut to 10 seeds and no ablations if needed |
| Frontend/backend contract drift | Late integration failure | Contract frozen at H1.5 with every type defined and float deliveries, mocks from day one, C codes against OpenAPI |
| Non-determinism (dict order, networkx version) | Irreproducible demo | Sorted iteration, integer costs, tie-break rule, pinned dependency versions, test I8 |
| Demo network does not show the story | Weak demo | B tunes the campus template at **H8 to H10**, after S0-QoS and S2 both run, so that, **verified by running**, the uplink failure overloads the backup under S0-QoS while S2 delivers more |
| Nothing visible sets the project apart | Weak Uniqueness score | Not solved by rigor. The visible differentiators are the fair-baseline comparison, the per-drop explanation with its max-flow check, and stating on stage where we only tie |
| Demo machine or setup failure | Disaster | Recorded video and a saved fallback run JSON that the UI can load |
| AI agents edit outside their folder, change the contract, or weaken tests | Silent breakage found at integration | Rules in section 11: shared `AGENTS.md`, folder ownership, human-only contract edits, hand-worked expected numbers, small commits |
| Scope creep | Missed core | Cut lines above; D can veto additions after H12 |
| Team fatigue | Bugs late | Staggered rest; no features after H16 |

### Fallback ladder
If S2 is not working at H8, ship priority ordering with splitting and no congestion cost. If the UI is not working at H12, demo from the CLI and generated HTML or charts from the benchmark output. If the live demo fails, play the recording.

---

## 14. Scalability and future roadmap

### Where time goes (to be confirmed by profiling, not assumed)
- **Shortest-path calls** dominate: about `F·(m + 1)` calls of O(E log V) each.
- **Repeated rerouting:** every event recomputes everything. Cost is `events × single-run cost`.
- **Candidate enumeration:** none in S2, which is a deliberate advantage over k-shortest-path designs.
- **Capacity accounting:** O(path length) per reservation, negligible.
- **Visualization:** Cytoscape handles a few hundred nodes; above that, hide labels, simplify styles, or render only the affected subgraph.

### Optimizations (roadmap only; not needed at the 50-node demo size unless H4 fails)
1. Aggregate flows with the same `(src, dst, class)`.
2. Replace networkx Dijkstra with a heapq version on integer node indices behind `pathfinder.py`.
3. After a **failure** event, reuse the allocation of flows ordered before the first affected flow. This is exact because they see the same ledger state and a removed non-chosen arc cannot change their shortest path. It does not hold for recovery events, where added arcs can change earlier choices.
4. Reduce the residual graph to arcs with residual above zero incrementally rather than rebuilding.

### Extensibility without a rewrite
- New policies register by name behind `RoutingPolicy`; the UI, API and benchmark pick them up automatically.
- New generators register behind a `TopologySpec` or `TrafficSpec` kind.
- Scenarios are data (JSON), so larger or new ones need no code.
- Metrics are pure functions of `(topology, flows, allocation)`.

### Roadmap (kept from the earlier plan, ordered by value)
1. LP reference and optimality gap (if not done).
1a. Scaling study: networks of 20 to 500 nodes and 50 to 2000 flows across several generators, with compute time plotted against `F·m·E`.
1b. Replace the greedy push loop with a per-flow min-cost max-flow so `greedy_gap` is zero by construction.
2. Vulnerability analyzer: bridges, articulation points, links ranked by P0 traffic carried.
3. Monte-Carlo robustness curve: fail k random links, plot DR_P0 against k per policy.
4. Rip-up and reroute to repair greedy mistakes.
5. What-if preview on hover; repair prioritizer.
6. Time-varying traffic and tick simulation; cascading failures when an arc stays overloaded.
7. Shared-risk link groups and precomputed disjoint backup paths for P0.
8. Real topology import (for example GraphML from public topology collections).
9. Natural-language command box.

Each item is independent of the core and can be added without changing the interfaces in section 7.

---

## 15. Definition of done and final demo script

### Definition of done (checklist)
- [ ] One command starts the backend, one command starts the frontend; README setup steps work on a clean machine.
- [ ] S0, S0-QoS, S1, S2 run on identical scenarios from the CLI and the UI.
- [ ] All invariants I1 to I11 pass on all fixtures and under hypothesis tests.
- [ ] The diamond worked example reproduces the exact numbers in section 4 for all three columns.
- [ ] Scenarios 1 to 8 run.
- [ ] Hypotheses H1 to H5 evaluated against S0-QoS and reported, including any that failed or tied.
- [ ] UI shows failure injection, side-by-side comparison with S0-QoS as the default baseline, KPIs, flow inspector with decision record.
- [ ] A network can be generated from the UI (size and seed) and failed interactively.
- [ ] Decision log shows reference path, attempts, cause, max-flow bound and greedy gap for every unserved flow, and the cut where the cause is insufficient capacity.
- [ ] README contains: model, algorithm and pseudocode, architecture diagram, how to reproduce a run from a seed, benchmark results, limitations, future work.
- [ ] Recorded fallback video and saved fallback run exist.
- [ ] A short "technical contribution" paragraph: residual-graph priority allocator, class-isolation guarantee, cut-based explanations checked against a max-flow bound, comparison against a QoS baseline, honest ablation and limitations.

### Demo script (2 to 3 minutes)

| Time | Show | Say |
|---|---|---|
| 0:00 to 0:20 | Click "Generate network" with a seed; healthy campus in both panels, green links, KPIs near 100% | "A generated campus network. Same traffic on both sides. Left: shortest-path routing with QoS priority queues, which is what a real network does. Right: ours." |
| 0:20 to 0:35 | Show flow table: P0 auth and emergency traffic highlighted | "Critical services are tagged. Everything else is best effort." |
| 0:35 to 1:00 | Click the primary uplink to fail it in both panels | "One link fails." |
| 1:00 to 1:35 | Left (S0-QoS): backup link in overload colour, critical traffic protected by the queue, academic and best-effort traffic dropped. Right (S2): load split over the remaining paths, no link overloaded, higher total and P1 delivery | "QoS alone protects critical traffic but everything still piles onto one backup link. Ours spreads it over capacity the shortest path ignores and delivers [value from our run] more." |
| 1:35 to 1:45 | Switch the left selector to plain S0 for a moment | "And without QoS, critical traffic is lost too." |
| 1:45 to 2:10 | Click a P2 flow that is unserved, show the decision record | "It tells you why: this link is saturated by critical traffic, and a max-flow check confirms nothing more could fit. Not a mystery drop." |
| 2:10 to 2:30 | Fail a link isolating a hostel | "Disconnected traffic is labelled as physical, not blamed on the algorithm." |
| 2:30 to 2:50 | Benchmark chart: DR against load factor for S0-QoS and S2, plus the limitation | "Across 30 seeds, total delivery improves by [value from our run] over the QoS baseline. On critical traffic alone we [match / beat] it, and here is where we only tie." |

**Rule:** every number spoken must come from the final benchmark run on the frozen code. If the numbers differ from the targets in section 9, say what they are. If the H8 check ended in the tie outcome, the 1:00 to 1:35 line becomes "same delivery as QoS, with no overloaded link and a reason for every drop".
