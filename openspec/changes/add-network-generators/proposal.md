## Why

The problem statement asks that users can create or generate a network topology, and the benchmark needs 30 reproducible networks of about 50 nodes and 200 flows. The demo also needs a hand-tuned campus network on which a single uplink failure leaves somewhere for traffic to go (PLAN.md assumption A1).

## What Changes

- Add a fixed **campus template** topology used for the demo and scenarios 1, 2, 5, 6, 8.
- Add one **campus generator**: `(buildings, redundancy, seed)` to a topology of about 50 nodes with a designated primary uplink.
- Add a **traffic generator**: `(n_flows, load_factor, class_mix, seed)` to a list of flows across P0, P1, P2, plus support for an explicit flow list.
- Add **load-factor scaling** of demands for the benchmark sweep (0.5 to 2.0).
- Add the **post-failure path check**: with the primary uplink failed, every building still has at least two node-disjoint paths to the core whose combined capacity exceeds that building's P0 plus P1 demand. The generator retries with the next seed, at most 20 times, then raises.
- Add resolution of `TopologySpec` and `TrafficSpec` to a concrete `Topology` and `list[Flow]`, with generators registered by name.

## Non-goals

- More than one generator family, real topology import, the scaling study (PLAN.md section 14 roadmap).
- Time-varying traffic.
- Scenario event lists and the eight scenario fixtures (`add-simulation-engine`).

## Capabilities

### New Capabilities
- `topology-generation`: campus template, seeded campus generator, spec resolution, and the post-failure path check.
- `traffic-generation`: seeded traffic generator with class mix, explicit flow lists, and load-factor scaling.

### Modified Capabilities

None.

## Impact

- **Owner:** B.
- **Folders:** `core/gen/` (including its tests in `core/gen/tests/`) and `fixtures/` for the campus template and its traffic.
- **PLAN.md sections implemented:** 2 (scope: topology and traffic generation), 7 (`TopologySpec`, `TrafficSpec`, reproducibility rules), 9 (demo-network path check, network size, load factor), 12 (H1.5 to H4 template, H8 to H10 tuning, H8 to H12 generator), 14 (generators register by kind).
- **Frozen contract:** touched. The campus template and its traffic are fixtures under `fixtures/`, added after the H1.5 freeze and changed again by the H8 to H10 tuning. Each of those edits needs all four members to agree, and the fixture changes before any code that reads it. `core/model/types.py` is not touched.
- **Depends on:** `add-core-model-contract` (types, arcs).
- **Depended on by:** `add-simulation-engine` (scenario loading), `add-rest-api` (generate-network control), `add-cli-benchmark` (seeds).
- **Window:** H1.5 to H12.
