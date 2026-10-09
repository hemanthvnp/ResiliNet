/**
 * Contract models defined in PLAN.md Section 7 and frozen at H1.5.
 * Strictly mirrors core/model/types.py and the OpenAPI schema.
 */

export type NodeKind = 'core' | 'distribution' | 'access' | 'service';
export type LinkStatus = 'up' | 'down';
export type FlowCause = 'NONE' | 'DISCONNECTED' | 'INSUFFICIENT_CAPACITY' | 'PATH_LIMIT' | 'OVERLOAD_LOSS';
export type OrderStrategy = 'arrival' | 'class_size_desc' | 'class_size_asc';

export interface Node {
  id: string;
  type: string;
  name: string;
}

export interface Link {
  id: string;
  u: string;
  v: string;
  capacity: number; // integer Mbps
  latency: number;  // integer ms
  status: LinkStatus;
}

export interface Topology {
  nodes: Node[];
  links: Link[];
}

export interface Flow {
  id: string;
  src: string;
  dst: string;
  rate: number;     // integer Mbps
  cls: number;      // 0 = P0 (Critical), 1 = P1 (Academic), 2 = P2 (Best Effort)
  service?: string; // e.g. "Auth / SIS", "Lab Cloud", "Guest Wifi"
}

export interface PathAlloc {
  arcs: string[];   // arc id format: "L7:u>v"
  rate: number;
}

export interface FlowResult {
  flow_id: string;
  paths: PathAlloc[];
  delivered: number; // float (can be fractional under S0/S0-QoS)
  unserved: number;  // float
  cause: FlowCause;
}

export interface Allocation {
  results: Record<string, FlowResult>;
  arc_load: Record<string, number>; // offered load per arc
}

export interface PolicyConfig {
  order: OrderStrategy;
  max_paths: number;
  congestion_lambda: number;
  util_cap: number;
}

export interface Event {
  step: number;
  kind: 'fail' | 'recover';
  links: string[];
  node?: string | null;
}

export interface Attempt {
  iter: number;
  arcs: string[];
  cost: number;
  latency: number;
  bottleneck: number;
  pushed: number;
}

export interface CutArc {
  arc: string;
  state: 'saturated' | 'down';
  load_by_class: Record<number, number>;
}

export interface DecisionRecord {
  flow_id: string;
  cls: number;
  demand: number;
  step: number;
  failed_links: string[];
  previous: PathAlloc[];
  reference_path: string[];
  reference_status: string;
  attempts: Attempt[];
  delivered: number;
  unserved: number;
  cause: string;
  cut: CutArc[];
  maxflow_bound?: number | null;
  greedy_gap?: number | null;
  explanation: string;
}

export interface Metrics {
  dr: number;                            // overall delivery ratio 0..1
  dr_by_class: Record<number, number>;   // 0: P0, 1: P1, 2: P2
  dr_reach: number;                      // delivery ratio for reachable flows only
  unserved_by_cause: Record<string, number>;
  overloaded_arcs: number;
  overload_excess: number;
  max_util: number;
  mean_util: number;
  arcs_above_90: number;
  link_util: Record<string, number>;      // per physical link (max of both arcs)
  latency_stretch: number;
  recovery_ratio?: number | null;
  churn_flows: number;
  churn_rate: number;
  p0_greedy_gap: number;
  compute_ms: number;
}

export interface Snapshot {
  step: number;
  link_state: Record<string, string>; // link_id -> "up" | "down"
  allocation: Allocation;
  metrics: Metrics;
  affected_flows: string[];
  decisions: DecisionRecord[];
}

export interface TemplateTopologySpec {
  template: string; // e.g. "campus"
}

export interface GeneratedTopologySpec {
  generator: string;
  buildings: number;
  redundancy: number;
  seed: number;
}

export type TopologySpec = TemplateTopologySpec | GeneratedTopologySpec;

export interface GeneratedTrafficSpec {
  generator: string;
  n_flows: number;
  load_factor: number;
  class_mix: Record<number, number>;
  seed: number;
}

export type TrafficSpec = Flow[] | GeneratedTrafficSpec;

// A scenario holds specs, not the resolved network: POST /runs returns the resolved
// topology and flows alongside it (RunResponse).
export interface Scenario {
  id: string;
  seed: number;
  topology: TopologySpec;
  traffic: TrafficSpec;
  events: Event[];
  config: PolicyConfig;
}

// --- API envelopes (api/schemas.py) -------------------------------------------

export interface ScenarioInfo {
  id: string;
  name: string;
  description: string;
}

export interface RunResponse {
  run_id: string;
  scenario: Scenario;
  topology: Topology;
  flows: Flow[];
  snapshot: Snapshot;
}

// The server assigns the step, so an event request carries none.
export type EventRequest = Omit<Event, 'step'>;

export interface CompareRow {
  policy: string;
  metrics: Metrics; // of the final step
}

export interface CompareResponse {
  scenario: Scenario;
  topology: Topology; // resolved, so a saved file renders with no server (task 5.2)
  flows: Flow[];
  table: CompareRow[];
  snapshots: Record<string, Snapshot[]>;
}

export interface RunSession {
  id: string;
  scenario_id: string;
  policy: 'S0' | 'S0-QoS' | 'S1' | 'S2';
  config: PolicyConfig;
  current_snapshot: Snapshot;
  history: Snapshot[];
}
