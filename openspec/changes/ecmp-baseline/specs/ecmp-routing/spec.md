# Spec Delta

## Purpose

ECMP-style baselines that split traffic equally across equal-cost next hops. S2 is compared under the same delivery models as S0 and S0-QoS against this load-spreading technique, which real routers use.

## ADDED Requirements

### Requirement: Equal-cost next hops
For each flow, the equal-cost next hops of a node u SHALL be its available arcs (u, v) with `latency(u, v) + dist(v) == dist(u)`, where `dist` is the latency-shortest distance to the flow's destination over available arcs.
- Next hops SHALL be ordered by (neighbour node id, link id).
- At most the first 8 SHALL be used at each node.
- A flow whose destination is unreachable SHALL have no allocation and cause `DISCONNECTED`.

Expected values: hand-worked from PLAN.md section 4 (diamond) and PLAN-CYCLE2.md section 3.1. A human re-checks them before tests are written.

#### Scenario: Two next hops on the square
- **WHEN** a flow from A to D is routed on the square (links A–B, B–D, A–C, C–D, each capacity 10, latency 1)
- **THEN** A has two next hops, B then C, and the flow uses paths A-B-D and A-C-D

#### Scenario: Single shortest path on the diamond
- **WHEN** the two diamond flows of PLAN.md section 4 are routed on the healthy diamond
- **THEN** each flow uses only A-B-D, the same route as S0, and the load on arcs A>B and B>D is 25

#### Scenario: Disconnected flow
- **WHEN** a flow's destination is unreachable
- **THEN** the flow has no paths, delivered 0 and cause `DISCONNECTED`

### Requirement: Integer split per next hop
Starting with the flow's rate at its source, the integer amount a arriving at each node SHALL be divided across its n next hops: `a // n` each, with the remaining `a % n` Mbps given one each to the first next hops in order. Branches that receive 0 SHALL be dropped. Each resulting source-to-destination path SHALL carry the integer amount that reaches the destination along it, and the path rates SHALL sum to the flow's rate.

Expected values: hand-worked, PLAN-CYCLE2.md sections 3.1 and 10 (C1.1).

#### Scenario: Odd rate on the square
- **WHEN** a 15 Mbps flow is split at A on the square
- **THEN** A-B-D carries 8 and A-C-D carries 7

#### Scenario: Shared first hop
- **WHEN** a 120 Mbps flow from S to D is routed on links S–A, A–X, X–D, A–Y, Y–D, S–B (each latency 1) and B–D (latency 2), all with capacity 100
- **THEN** S splits 60 to A and 60 to B, A splits 30 to X and 30 to Y
- **AND** the paths are S-A-X-D 30, S-A-Y-D 30 and S-B-D 60
- **AND** the arc loads are S>A 60, S>B 60, B>D 60, and 30 on each of A>X, X>D, A>Y and Y>D

#### Scenario: Eight next hops at one node
- **WHEN** one 100 Mbps flow from S to T is routed on eight parallel routes S→Ri→T (i = 1..8), each link with capacity 10 and latency 1
- **THEN** the paths via R1 to R4 carry 13 each and the paths via R5 to R8 carry 12 each

### Requirement: Proportional delivery (ECMP)
`ECMP` SHALL deliver, for each path, its rate times `min over arcs on the path of min(1, capacity / load)`, where load is the offered load from all flows. A flow's delivery SHALL be the sum over its paths. A flow that loses traffic SHALL have cause `OVERLOAD_LOSS`. `arc_load` SHALL be the offered load.

Expected values: hand-worked, PLAN-CYCLE2.md section 3.1, using the S0 formula of PLAN.md section 5.

#### Scenario: Square, healthy
- **WHEN** `ECMP` routes F1 (P0, 15 Mbps, A→D) and F2 (P2, 10 Mbps, A→D) on the square
- **THEN** the offered load is 13 on A>B and B>D and 12 on A>C and C>D
- **AND** F1 delivers 80/13 + 70/12 (about 11.987179) and F2 delivers 50/13 + 50/12 (about 8.012821), within 1e-9
- **AND** total delivery is 20 of 25 (`DR` 0.80) and 4 arcs are overloaded

#### Scenario: Diamond equals S0
- **WHEN** `ECMP` and S0 route the same flows on the healthy diamond
- **THEN** every flow's delivery is equal (F1 6, F2 4)

### Requirement: Strict-priority delivery (ECMP-QoS)
`ECMP-QoS` SHALL use exactly the routes and offered load of `ECMP`. On each arc, class k SHALL get `max(0, capacity − load of all higher classes)`, with scale 1 when class k has no load on the arc and `min(1, available / load of class k)` otherwise. Each path SHALL deliver its rate times the minimum scale of its flow's class over its arcs, and a flow's delivery SHALL be the sum over its paths.

Expected values: hand-worked, PLAN-CYCLE2.md sections 3.1 and 10 (C2.1), using the S0-QoS rule of PLAN.md section 5.

#### Scenario: Square, healthy
- **WHEN** `ECMP-QoS` routes F1 (P0, 15) and F2 (P2, 10) from A to D on the square
- **THEN** F1 delivers 15 and F2 delivers 5 (2 via B, 3 via C)
- **AND** `DR` is 0.80, `DR_P0` is 1.00 and 4 arcs are overloaded

#### Scenario: Diamond equals S0-QoS
- **WHEN** `ECMP-QoS` and S0-QoS route the same flows on the healthy diamond
- **THEN** F1 delivers 10 and F2 delivers 0 under both

#### Scenario: Eight parallel routes, ECMP-QoS can beat S2
- **WHEN** the eight-route topology above carries one P0 flow of 100 Mbps from S to T
- **THEN** `ECMP-QoS` delivers 80 (10 on each route), with 16 overloaded arcs and total excess 40
- **AND** S0-QoS delivers 10, with 2 overloaded arcs
- **AND** S2 with the default `max_paths` 3 delivers 30 with 0 overloaded arcs, with 70 unserved, cause `PATH_LIMIT` and greedy gap 50
- **AND** S2 with `max_paths` 8 delivers 80 with 0 overloaded arcs

### Requirement: Registered, pure and deterministic
`ECMP` and `ECMP-QoS` SHALL be selectable by those names wherever S0 to S2 are selectable through `python -m ext`. They SHALL be pure: identical input gives identical output, with no clock, no global state and no randomness. Every snapshot they produce SHALL pass `check_invariants`, except the capacity invariant I4, which applies only to S1 and S2.

Source: PLAN.md sections 7, 9 and 14.

#### Scenario: Compare includes ECMP
- **WHEN** `python -m ext compare --scenario examples/square.json --policies S0-QoS ECMP-QoS S2` is run
- **THEN** three rows are printed with `DR` 0.40, 0.80 and 0.80

#### Scenario: Repeat run
- **WHEN** `ECMP-QoS` routes the same input twice
- **THEN** the two allocations are equal

#### Scenario: Invariants on random scenarios
- **WHEN** hypothesis draws random seeded campus scenarios and event lists
- **THEN** every `ECMP` and `ECMP-QoS` snapshot passes `check_invariants` (I4 excluded)
