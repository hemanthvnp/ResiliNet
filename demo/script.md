# Demo script (2 to 3 minutes)

PLAN.md section 15, filled with numbers from the final runs. Every number below comes from:
- the 30-seed benchmark in `results/` (commit `f45c9c0`; `core/` and `cli/` unchanged since), or
- the named scenario, run on the same code.

If a number on screen differs from what is written here, say what the screen shows.

**Setup** (C, demo laptop):
- Backend: `uvicorn api.app:app --port 8000`.
- Frontend: `cd frontend && npm run dev`.
- Open <http://localhost:5173/?scenario=02_uplink_failure&demo=1>.
- **If the live demo fails:** "Load saved run", then `demo/fallback.json`, which needs no server. It holds S0-QoS, S0 and S2 on `02_uplink_failure`, with step 0 healthy and step 1 with L6 failed.

| Time | Show | Say |
|---|---|---|
| 0:00 to 0:20 | `02_uplink_failure`, healthy: green links, every KPI at 100% in both panels | "Our campus network. Same traffic on both sides. Left: shortest-path routing with QoS priority queues, which is what a real network does. Right: ours." |
| 0:20 to 0:35 | The flow table, with the P0 auth and emergency flows highlighted | "Critical services are tagged P0. Academic traffic is P1, and everything else is best effort." |
| 0:35 to 1:00 | Click L6, the primary uplink, to fail it in both panels | "One link fails." |
| 1:00 to 1:35 | Left (S0-QoS): DR 70.6%, P1 75%, one link at 225% in the overload colour. Right (S2): DR 100%, P1 100%, no link overloaded | "QoS alone protects critical traffic, but everything still piles onto one backup link. Ours spreads it over capacity the shortest path ignores and delivers everything." |
| 1:35 to 1:45 | Switch the left selector to S0 | "And without QoS, critical traffic is lost too: P0 drops to 72%." |
| 1:45 to 2:10 | "Generate network" (37 buildings, redundancy 0.5, seed 1). Click F119, an unserved P2 flow, in the S2 panel | "A generated 50-node campus. Even healthy, the QoS baseline delivers 84% with 18 overloaded links; ours delivers 97% with none. This flow is unserved, and the record says why: link L111 is full with critical and academic traffic, and the max-flow check confirms nothing more could fit. Not a mystery drop." |
| 2:10 to 2:30 | `06_disconnected`: fail L20, the Boys' hostel link | "Disconnected traffic is labelled as physical: 5 Mbps can no longer reach anywhere, and delivery to everything still reachable stays at 100%. That loss is not blamed on the algorithm." |
| 2:30 to 2:50 | "Load benchmark CSV", then `results/benchmark.csv`; the chart shows case `uplink`, DR against load factor for S0-QoS and S2 | "Across 30 generated networks, under a failed uplink or three failed links, we deliver 14 points more than the QoS baseline, with a 95% interval of 13 to 15. On critical traffic alone we tie, and only pull ahead at twice the normal load. Our policy never overloaded a link in 1800 runs." |

**Rule (PLAN.md section 15):** every number spoken comes from the final benchmark run on the frozen code. If the code changes before submission, rerun the benchmark and this table.

## Likely judge questions

| Question | Answer, with its source |
|---|---|
| "Is the baseline a strawman?" | No. S0-QoS is shortest path with strict priority queues per link, and every headline number is quoted against it. |
| "Where do you only tie?" | Critical (P0) delivery: +0.00 points at normal load (H1b). We pull ahead only at twice the normal load (+1.2 to +1.4). With only one path left, rerouting cannot create capacity (the PLAN.md section 4 diamond). |
| "Did any hypothesis fail?" | H2 failed, in our favour. It said that with no congestion S2 would be within 1 point of S0-QoS, but S2 delivered 2.1 points more (95% CI 1.6 to 2.6), because shortest-path routing already overloads some links at load 0.5. |
| "How fast is it?" | The median recompute at 50 nodes and 200 flows is 51 ms (H4). The whole 30-seed benchmark, with 3960 rows, ran in 88 s. |
| "Is the greedy optimal?" | No. But the P0 greedy gap was zero in all 720 default S2 runs (H5), and every unserved flow reports its own gap. |
| "Which single link hurts most?" | `python -m ext sweep --scenario 01_normal`. S2 keeps every P0 flow for every single failure of a non-bridge link. S0-QoS's worst case is the primary uplink L6. The bridges (the core-to-service links and the hostel links) are listed separately. |
