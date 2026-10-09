import { Topology, Flow, Snapshot } from '../types/contract';

export const CAMPUS_TOPOLOGY: Topology = {
  nodes: [
    { id: 'N_CORE1', type: 'core', name: 'Core Router 1' },
    { id: 'N_CORE2', type: 'core', name: 'Core Router 2' },
    { id: 'N_DIST_N', type: 'distribution', name: 'North Dist' },
    { id: 'N_DIST_S', type: 'distribution', name: 'South Dist' },
    { id: 'N_CS_ENG', type: 'access', name: 'CS & Engineering' },
    { id: 'N_LIB', type: 'access', name: 'Central Library' },
    { id: 'N_ADMIN', type: 'access', name: 'Admin / Auth' },
    { id: 'N_HOSTEL', type: 'access', name: 'Hostel Block' },
    { id: 'N_DC', type: 'service', name: 'Campus DataCenter' },
  ],
  links: [
    // Core interconnect
    { id: 'L_CORE_INTER', u: 'N_CORE1', v: 'N_CORE2', capacity: 2000, latency: 1, status: 'up' },
    // Primary & backup uplinks to DC
    { id: 'L_DC_PRI', u: 'N_CORE1', v: 'N_DC', capacity: 1500, latency: 2, status: 'up' },
    { id: 'L_DC_BCK', u: 'N_CORE2', v: 'N_DC', capacity: 1000, latency: 4, status: 'up' },
    // Distribution to Core
    { id: 'L_DIST_N_C1', u: 'N_DIST_N', v: 'N_CORE1', capacity: 1000, latency: 3, status: 'up' },
    { id: 'L_DIST_N_C2', u: 'N_DIST_N', v: 'N_CORE2', capacity: 1000, latency: 4, status: 'up' },
    { id: 'L_DIST_S_C1', u: 'N_DIST_S', v: 'N_CORE1', capacity: 1000, latency: 3, status: 'up' },
    { id: 'L_DIST_S_C2', u: 'N_DIST_S', v: 'N_CORE2', capacity: 1000, latency: 4, status: 'up' },
    // Access to Distribution
    { id: 'L_CS_DIST', u: 'N_CS_ENG', v: 'N_DIST_N', capacity: 800, latency: 2, status: 'up' },
    { id: 'L_LIB_DIST', u: 'N_LIB', v: 'N_DIST_N', capacity: 600, latency: 2, status: 'up' },
    { id: 'L_ADM_DIST', u: 'N_ADMIN', v: 'N_DIST_S', capacity: 500, latency: 2, status: 'up' },
    { id: 'L_HST_DIST', u: 'N_HOSTEL', v: 'N_DIST_S', capacity: 500, latency: 3, status: 'up' },
    // Cross-link for multi-path redundancy
    { id: 'L_X_DIST', u: 'N_DIST_N', v: 'N_DIST_S', capacity: 600, latency: 3, status: 'up' },
  ],
};

export const INITIAL_FLOWS: Flow[] = [
  { id: 'F01', src: 'N_ADMIN', dst: 'N_DC', rate: 150, cls: 0, service: 'Auth & Directory (P0)' },
  { id: 'F02', src: 'N_CS_ENG', dst: 'N_DC', rate: 300, cls: 0, service: 'Emergency Alert (P0)' },
  { id: 'F03', src: 'N_CS_ENG', dst: 'N_DC', rate: 450, cls: 1, service: 'Research Cloud (P1)' },
  { id: 'F04', src: 'N_LIB', dst: 'N_DC', rate: 350, cls: 1, service: 'Digital Library (P1)' },
  { id: 'F05', src: 'N_HOSTEL', dst: 'N_DC', rate: 500, cls: 2, service: 'Hostel Streaming (P2)' },
  { id: 'F06', src: 'N_CS_ENG', dst: 'N_HOSTEL', rate: 200, cls: 2, service: 'P2P File Transfer (P2)' },
];

/**
 * Step 0 Healthy Snapshot
 */
export const MOCK_STEP0_SNAPSHOT: Snapshot = {
  step: 0,
  link_state: {
    L_CORE_INTER: 'up',
    L_DC_PRI: 'up',
    L_DC_BCK: 'up',
    L_DIST_N_C1: 'up',
    L_DIST_N_C2: 'up',
    L_DIST_S_C1: 'up',
    L_DIST_S_C2: 'up',
    L_CS_DIST: 'up',
    L_LIB_DIST: 'up',
    L_ADM_DIST: 'up',
    L_HST_DIST: 'up',
    L_X_DIST: 'up',
  },
  allocation: {
    results: {
      F01: {
        flow_id: 'F01',
        paths: [{ arcs: ['L_ADM_DIST:N_ADMIN>N_DIST_S', 'L_DIST_S_C1:N_DIST_S>N_CORE1', 'L_DC_PRI:N_CORE1>N_DC'], rate: 150 }],
        delivered: 150,
        unserved: 0,
        cause: 'NONE',
      },
      F02: {
        flow_id: 'F02',
        paths: [{ arcs: ['L_CS_DIST:N_CS_ENG>N_DIST_N', 'L_DIST_N_C1:N_DIST_N>N_CORE1', 'L_DC_PRI:N_CORE1>N_DC'], rate: 300 }],
        delivered: 300,
        unserved: 0,
        cause: 'NONE',
      },
      F03: {
        flow_id: 'F03',
        paths: [{ arcs: ['L_CS_DIST:N_CS_ENG>N_DIST_N', 'L_DIST_N_C1:N_DIST_N>N_CORE1', 'L_DC_PRI:N_CORE1>N_DC'], rate: 450 }],
        delivered: 450,
        unserved: 0,
        cause: 'NONE',
      },
      F04: {
        flow_id: 'F04',
        paths: [{ arcs: ['L_LIB_DIST:N_LIB>N_DIST_N', 'L_DIST_N_C2:N_DIST_N>N_CORE2', 'L_DC_BCK:N_CORE2>N_DC'], rate: 350 }],
        delivered: 350,
        unserved: 0,
        cause: 'NONE',
      },
      F05: {
        flow_id: 'F05',
        paths: [{ arcs: ['L_HST_DIST:N_HOSTEL>N_DIST_S', 'L_DIST_S_C2:N_DIST_S>N_CORE2', 'L_DC_BCK:N_CORE2>N_DC'], rate: 500 }],
        delivered: 500,
        unserved: 0,
        cause: 'NONE',
      },
      F06: {
        flow_id: 'F06',
        paths: [{ arcs: ['L_CS_DIST:N_CS_ENG>N_DIST_N', 'L_X_DIST:N_DIST_N>N_DIST_S', 'L_HST_DIST:N_DIST_S>N_HOSTEL'], rate: 200 }],
        delivered: 200,
        unserved: 0,
        cause: 'NONE',
      },
    },
    arc_load: {
      'L_DC_PRI:N_CORE1>N_DC': 900,
      'L_DC_BCK:N_CORE2>N_DC': 850,
    },
  },
  metrics: {
    dr: 1.0,
    dr_by_class: { 0: 1.0, 1: 1.0, 2: 1.0 },
    dr_reach: 1.0,
    unserved_by_cause: { NONE: 0 },
    overloaded_arcs: 0,
    overload_excess: 0,
    max_util: 0.85,
    mean_util: 0.42,
    arcs_above_90: 0,
    link_util: {
      L_CORE_INTER: 0.15,
      L_DC_PRI: 0.60,
      L_DC_BCK: 0.85,
      L_DIST_N_C1: 0.75,
      L_DIST_N_C2: 0.35,
      L_DIST_S_C1: 0.15,
      L_DIST_S_C2: 0.50,
      L_CS_DIST: 0.94,
      L_LIB_DIST: 0.58,
      L_ADM_DIST: 0.30,
      L_HST_DIST: 0.70,
      L_X_DIST: 0.33,
    },
    latency_stretch: 1.0,
    recovery_ratio: null,
    churn_flows: 0,
    churn_rate: 0,
    p0_greedy_gap: 0.0,
    compute_ms: 12.4,
  },
  affected_flows: [],
  decisions: [
    {
      flow_id: 'F01',
      cls: 0,
      demand: 150,
      step: 0,
      failed_links: [],
      previous: [],
      reference_path: ['L_ADM_DIST:N_ADMIN>N_DIST_S', 'L_DIST_S_C1:N_DIST_S>N_CORE1', 'L_DC_PRI:N_CORE1>N_DC'],
      reference_status: 'VALID',
      attempts: [{ iter: 1, arcs: ['L_ADM_DIST:N_ADMIN>N_DIST_S', 'L_DIST_S_C1:N_DIST_S>N_CORE1', 'L_DC_PRI:N_CORE1>N_DC'], cost: 7, latency: 7, bottleneck: 500, pushed: 150 }],
      delivered: 150,
      unserved: 0,
      cause: 'NONE',
      cut: [],
      maxflow_bound: 150,
      greedy_gap: 0.0,
      explanation: 'F01 (P0, 150 Mbps): routed on shortest path (latency 7 ms). 150 Mbps delivered.',
    },
  ],
};

/**
 * Step 1: Primary DC Uplink (L_DC_PRI) Failed
 * Under S2: Traffic reroutes and splits across backup and core interconnect with ZERO overloads.
 */
export const MOCK_STEP1_S2_SNAPSHOT: Snapshot = {
  step: 1,
  link_state: {
    ...MOCK_STEP0_SNAPSHOT.link_state,
    L_DC_PRI: 'down',
  },
  allocation: {
    results: {
      ...MOCK_STEP0_SNAPSHOT.allocation.results,
      F02: {
        flow_id: 'F02',
        paths: [{ arcs: ['L_CS_DIST:N_CS_ENG>N_DIST_N', 'L_DIST_N_C2:N_DIST_N>N_CORE2', 'L_DC_BCK:N_CORE2>N_DC'], rate: 300 }],
        delivered: 300,
        unserved: 0,
        cause: 'NONE',
      },
      F03: {
        flow_id: 'F03',
        paths: [
          { arcs: ['L_CS_DIST:N_CS_ENG>N_DIST_N', 'L_DIST_N_C2:N_DIST_N>N_CORE2', 'L_DC_BCK:N_CORE2>N_DC'], rate: 250 },
          { arcs: ['L_CS_DIST:N_CS_ENG>N_DIST_N', 'L_X_DIST:N_DIST_N>N_DIST_S', 'L_DIST_S_C2:N_DIST_S>N_CORE2', 'L_DC_BCK:N_CORE2>N_DC'], rate: 200 },
        ],
        delivered: 450,
        unserved: 0,
        cause: 'NONE',
      },
    },
    arc_load: {
      'L_DC_BCK:N_CORE2>N_DC': 980,
    },
  },
  metrics: {
    dr: 0.98,
    dr_by_class: { 0: 1.0, 1: 1.0, 2: 0.94 },
    dr_reach: 0.98,
    unserved_by_cause: { INSUFFICIENT_CAPACITY: 30 },
    overloaded_arcs: 0,
    overload_excess: 0,
    max_util: 0.98,
    mean_util: 0.62,
    arcs_above_90: 1,
    link_util: {
      ...MOCK_STEP0_SNAPSHOT.metrics.link_util,
      L_DC_PRI: 0.0,
      L_DC_BCK: 0.98,
      L_DIST_N_C2: 0.88,
      L_CORE_INTER: 0.45,
    },
    latency_stretch: 1.25,
    recovery_ratio: 0.98,
    churn_flows: 3,
    churn_rate: 650,
    p0_greedy_gap: 0.0,
    compute_ms: 18.2,
  },
  affected_flows: ['F01', 'F02', 'F03'],
  decisions: [
    {
      flow_id: 'F03',
      cls: 1,
      demand: 450,
      step: 1,
      failed_links: ['L_DC_PRI'],
      previous: [{ arcs: ['L_CS_DIST:N_CS_ENG>N_DIST_N', 'L_DIST_N_C1:N_DIST_N>N_CORE1', 'L_DC_PRI:N_CORE1>N_DC'], rate: 450 }],
      reference_path: ['L_CS_DIST:N_CS_ENG>N_DIST_N', 'L_DIST_N_C1:N_DIST_N>N_CORE1', 'L_DC_PRI:N_CORE1>N_DC'],
      reference_status: 'INVALID: L_DC_PRI down',
      attempts: [
        { iter: 1, arcs: ['L_CS_DIST:N_CS_ENG>N_DIST_N', 'L_DIST_N_C2:N_DIST_N>N_CORE2', 'L_DC_BCK:N_CORE2>N_DC'], cost: 10, latency: 10, bottleneck: 250, pushed: 250 },
        { iter: 2, arcs: ['L_CS_DIST:N_CS_ENG>N_DIST_N', 'L_X_DIST:N_DIST_N>N_DIST_S', 'L_DIST_S_C2:N_DIST_S>N_CORE2', 'L_DC_BCK:N_CORE2>N_DC'], cost: 13, latency: 13, bottleneck: 200, pushed: 200 },
      ],
      delivered: 450,
      unserved: 0,
      cause: 'NONE',
      cut: [],
      maxflow_bound: 450,
      greedy_gap: 0.0,
      explanation: 'F03 (P1, 450 Mbps): path via Core1 invalid (L_DC_PRI down). Split across 2 paths: 250 Mbps via DistN-Core2, 200 Mbps via DistS-Core2. 450 Mbps delivered.',
    },
  ],
};

/**
 * Step 1 under Baseline S0-QoS:
 * All flows pile blindly onto L_DC_BCK causing massive overload (util = 1.75).
 */
export const MOCK_STEP1_S0_QOS_SNAPSHOT: Snapshot = {
  step: 1,
  link_state: {
    ...MOCK_STEP0_SNAPSHOT.link_state,
    L_DC_PRI: 'down',
  },
  allocation: {
    results: {
      ...MOCK_STEP0_SNAPSHOT.allocation.results,
      F03: {
        flow_id: 'F03',
        paths: [{ arcs: ['L_CS_DIST:N_CS_ENG>N_DIST_N', 'L_DIST_N_C2:N_DIST_N>N_CORE2', 'L_DC_BCK:N_CORE2>N_DC'], rate: 180 }],
        delivered: 180,
        unserved: 270,
        cause: 'OVERLOAD_LOSS',
      },
      F05: {
        flow_id: 'F05',
        paths: [{ arcs: ['L_HST_DIST:N_HOSTEL>N_DIST_S', 'L_DIST_S_C2:N_DIST_S>N_CORE2', 'L_DC_BCK:N_CORE2>N_DC'], rate: 0 },],
        delivered: 0,
        unserved: 500,
        cause: 'OVERLOAD_LOSS',
      },
    },
    arc_load: {
      'L_DC_BCK:N_CORE2>N_DC': 1750,
    },
  },
  metrics: {
    dr: 0.65,
    dr_by_class: { 0: 1.0, 1: 0.55, 2: 0.0 },
    dr_reach: 0.65,
    unserved_by_cause: { OVERLOAD_LOSS: 770 },
    overloaded_arcs: 1,
    overload_excess: 750,
    max_util: 1.75, // OVERLOAD! > 1.0
    mean_util: 0.78,
    arcs_above_90: 2,
    link_util: {
      ...MOCK_STEP0_SNAPSHOT.metrics.link_util,
      L_DC_PRI: 0.0,
      L_DC_BCK: 1.75, // Overloaded link!
    },
    latency_stretch: 1.15,
    recovery_ratio: 0.65,
    churn_flows: 5,
    churn_rate: 1400,
    p0_greedy_gap: 0.0,
    compute_ms: 2.1,
  },
  affected_flows: ['F01', 'F02', 'F03'],
  decisions: [
    {
      flow_id: 'F03',
      cls: 1,
      demand: 450,
      step: 1,
      failed_links: ['L_DC_PRI'],
      previous: [],
      reference_path: ['L_CS_DIST:N_CS_ENG>N_DIST_N', 'L_DIST_N_C2:N_DIST_N>N_CORE2', 'L_DC_BCK:N_CORE2>N_DC'],
      reference_status: 'VALID',
      attempts: [],
      delivered: 180,
      unserved: 270,
      cause: 'OVERLOAD_LOSS',
      cut: [],
      maxflow_bound: null, // baselines leave the bound and gap empty (DecisionRecord in types.py)
      greedy_gap: null,
      explanation: 'F03 (P1, 450 Mbps): S0-QoS queue scaled down due to 1.75x overload on L_DC_BCK. 270 Mbps lost to overload queueing.',
    },
  ],
};
