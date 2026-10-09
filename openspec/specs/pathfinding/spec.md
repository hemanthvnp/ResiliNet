# pathfinding Specification

## Purpose
TBD - created by archiving change add-routing-policies. Update Purpose after archive.
## Requirements
### Requirement: Deterministic shortest path
The pathfinder SHALL return the minimum-cost simple path between two nodes over a given set of arcs and integer arc weights. Ties SHALL be broken by `(cost, hop count, node id sequence)`. It SHALL return no path when the destination is unreachable.

Expected values: hand-worked from the diamond in PLAN.md section 4 (A-B-D costs 1 + 1 = 2). The tie-break rule is in section 7.

#### Scenario: Lowest cost wins
- **WHEN** the diamond is searched from A to D on latency
- **THEN** the path A-B-D with cost 2 is returned

#### Scenario: Equal cost, fewer hops wins
- **WHEN** two paths have equal cost and different hop counts
- **THEN** the path with fewer hops is returned

#### Scenario: Equal cost and hops, node ids decide
- **WHEN** two paths have equal cost and equal hop count
- **THEN** the path whose node id sequence sorts first is returned, on every run

#### Scenario: Parallel links
- **WHEN** two links join the same pair of nodes with different latency
- **THEN** the arc of the lower-latency link is used

#### Scenario: Down link is not used
- **WHEN** the search is given only available arcs and the shortest route crosses a down link
- **THEN** the returned path avoids that link

#### Scenario: No path
- **WHEN** source and destination are in different components
- **THEN** no path is returned

### Requirement: Connected components
The pathfinder SHALL compute the connected components of the available graph so that disconnection can be decided without a path search.

Source: PLAN.md section 5.

#### Scenario: Isolated node
- **WHEN** every link incident to a node is down
- **THEN** that node is in a component by itself

### Requirement: Residual reachability
The pathfinder SHALL return the set of nodes reachable from a source over arcs with residual capacity above zero.

Source: PLAN.md section 5.

#### Scenario: Saturated arc blocks reachability
- **WHEN** the only arc leaving the source has residual 0
- **THEN** the reachable set contains only the source

### Requirement: Max-flow value
The pathfinder SHALL return the maximum flow value between two nodes for given integer arc capacities.

Expected values: worked from the definitions in PLAN.md section 4 (two disjoint diamond paths of capacity 10 give 20), not from code; the owner confirms them by hand before the test is written.

#### Scenario: Diamond max-flow
- **WHEN** max-flow from A to D is computed on the healthy diamond with capacities 10
- **THEN** the value is 20

### Requirement: Single wrapper for graph algorithms
All calls to networkx SHALL be made from `core/routing/pathfinder.py` (generators excepted).

Source: PLAN.md section 6.

#### Scenario: No direct networkx use in policies
- **WHEN** the routing policy modules are inspected
- **THEN** none of them imports networkx

