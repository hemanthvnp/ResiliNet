## ADDED Requirements

### Requirement: Topology graph
The UI SHALL draw the topology as a graph with one edge per physical link. Edge colour SHALL come from `metrics.link_util` on a green-to-red scale, with a distinct overload colour for values above 1.0. Failed links SHALL be drawn red and dashed. Edge thickness SHALL reflect capacity. Key-service nodes SHALL be labelled.

Source: PLAN.md section 7 (link display rule) and 10.

#### Scenario: Utilization colouring
- **WHEN** a snapshot reports `link_util` 0.2 for one link and 0.95 for another
- **THEN** the first is drawn near the green end and the second near the red end of the scale

#### Scenario: Overloaded link
- **WHEN** a baseline snapshot reports `link_util` 2.5 for a link
- **THEN** that link is drawn in the overload colour

#### Scenario: Failed link
- **WHEN** a link's state is `down`
- **THEN** it is drawn red and dashed regardless of utilization

### Requirement: Values come from the backend
The UI SHALL display utilization, metrics, causes and explanations exactly as returned by the API and SHALL NOT compute them.

Source: PLAN.md section 7 (link display rule).

#### Scenario: Link colour source
- **WHEN** a snapshot is rendered
- **THEN** each edge's colour is determined by its `link_util` entry alone

### Requirement: Click to fail and recover
Clicking an up link SHALL send a fail event for it, and clicking a down link SHALL send a recover event. The view SHALL update from the returned snapshot.

Source: PLAN.md section 10.

#### Scenario: Fail a link
- **WHEN** the user clicks an up link
- **THEN** a fail event for that link is sent and the link is shown as failed after the response

#### Scenario: Recover a link
- **WHEN** the user clicks a failed link
- **THEN** a recover event is sent and the link is shown as up after the response

### Requirement: Side-by-side comparison
The UI SHALL show the same network under a baseline policy and under S2 at the same time, in the same layout, and SHALL apply every event to both. The baseline panel SHALL offer a selector between S0-QoS, the default, and S0.

Source: PLAN.md section 10.

#### Scenario: Event applied to both panels
- **WHEN** the user fails a link in either panel
- **THEN** both panels show that link as failed and both show the same step

#### Scenario: Default baseline
- **WHEN** the comparison view opens
- **THEN** the left panel shows S0-QoS and the right panel shows S2

#### Scenario: Switch baseline
- **WHEN** the user selects S0 after two events have been applied
- **THEN** the left panel shows S0 at the same step with the same links failed

### Requirement: KPI strip
Each panel SHALL show DR, DR_P0, DR_P1, the number of overloaded links and unserved traffic by cause, from that panel's snapshot.

Source: PLAN.md section 10.

#### Scenario: KPIs after a failure
- **WHEN** a failure event completes
- **THEN** each panel's KPI strip shows the values of its own new snapshot

### Requirement: Flow table
The UI SHALL list flows with class colour, service label, demand, delivered rate and status.

Source: PLAN.md section 10.

#### Scenario: Unserved flow
- **WHEN** a flow has unserved demand with cause `INSUFFICIENT_CAPACITY`
- **THEN** its row shows the delivered rate below demand and that cause as status

### Requirement: Flow inspection
Selecting a flow SHALL highlight its routes on the graph and open its decision record, showing the one-line explanation, the attempts, the cause, and for unserved S2 flows the max-flow bound and greedy gap.

Source: PLAN.md section 10.

#### Scenario: Inspect a split flow
- **WHEN** the user selects a flow carried on two paths
- **THEN** both paths are highlighted on the graph

#### Scenario: Inspect an unserved flow
- **WHEN** the user selects an unserved flow in the S2 panel
- **THEN** the decision panel shows the explanation text from the record and its max-flow bound

#### Scenario: Disconnected flow
- **WHEN** the user selects a flow with cause `DISCONNECTED`
- **THEN** the panel shows it as physically disconnected

### Requirement: Scenario selection, seed and reset
The UI SHALL let the user pick a built-in scenario, SHALL display the seed in use, and SHALL offer a reset that returns both panels to step 0.

Source: PLAN.md section 10.

#### Scenario: Reset
- **WHEN** the user presses reset after failing links
- **THEN** both panels show all links up and the step-0 metrics

#### Scenario: Seed shown
- **WHEN** a scenario is loaded
- **THEN** its seed is visible on screen

### Requirement: Generate a network
The UI SHALL provide a form with number of buildings, redundancy and seed that requests a generated network and loads it in both panels.

Source: PLAN.md section 10.

#### Scenario: Generate
- **WHEN** the user submits the form with a seed
- **THEN** both panels show the generated network and the effective seed is displayed

#### Scenario: Same seed again
- **WHEN** the user submits the same values a second time
- **THEN** the same network is shown

### Requirement: Works against mock and live API
The UI SHALL run unchanged against the API in mock mode and in live mode.

Source: PLAN.md section 12.

#### Scenario: Mock data
- **WHEN** the API runs in mock mode
- **THEN** the graph, KPI strip and flow table render from the mocked snapshot

### Requirement: Errors and loading are visible
While a request is in flight the UI SHALL show a loading state and ignore further link clicks. If a request fails it SHALL show an error message and keep the last good snapshot.

Source: a design decision of this change (design.md); PLAN.md does not specify it.

#### Scenario: Request fails
- **WHEN** an event request returns an error
- **THEN** an error message is shown and both panels still show the previous step

### Requirement: Fallback run
The UI SHALL be able to load a saved run file and display its snapshots without a server.

Source: PLAN.md section 13.

#### Scenario: Load saved run
- **WHEN** the user loads a saved comparison file with the backend stopped
- **THEN** both panels render the saved snapshots

### Requirement: Animated flow routes
When a flow is selected, each panel SHALL animate that flow's routes in its own snapshot: moving dashes in the flow's class colour, with line thickness proportional to the Mbps the flow carries on each link. On a link that is overloaded in that panel (utilization above 1), the flow's dashes SHALL be drawn red and sparse to show traffic lost there. The UI SHALL state that the animation shows computed rates along routes (a fluid model), not individual packets.

Source: a design decision of this change, added after the manual UI test (design.md); PLAN.md section 2 fixes the fluid model.

#### Scenario: Split flow
- **WHEN** a flow with two paths is selected
- **THEN** the links of both paths are animated, and a link carrying more of the flow's rate is drawn thicker

#### Scenario: Loss on an overloaded link
- **WHEN** a selected flow crosses a link whose utilization is above 1 in the baseline panel
- **THEN** that link is drawn with red, sparse dashes in the baseline panel only

### Requirement: Stage player for the last event
After an event, the UI SHALL offer three stages for it, shown in both panels: Before (the previous step), Link fails (the previous routes with the event's link state, and the paths of the affected flows marked), and Rerouted (the current step). Each stage SHALL carry a caption built from the snapshots: the failed or recovered links, the number of affected flows, and each panel's delivery, overloaded links and largest utilization.

Source: a design decision of this change, added after the manual UI test (design.md).

#### Scenario: Three stages of a failure
- **WHEN** a link has been failed and the user steps through the stages
- **THEN** Before shows the previous step, Link fails shows the failed link down with the affected flows' old paths marked and names the number of affected flows from the snapshot, and Rerouted shows the current step with each panel's delivery and overloaded links

#### Scenario: Leaving the player
- **WHEN** the user closes the stage player or applies another event
- **THEN** both panels show the current step
