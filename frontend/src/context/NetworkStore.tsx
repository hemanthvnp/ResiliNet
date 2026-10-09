import React, { createContext, useContext, useReducer, ReactNode } from 'react';
import { Topology, Flow, Snapshot, Event } from '../types/contract';

export type BaselinePolicy = 'S0-QoS' | 'S0';

export interface PanelState {
  policy: string;
  runId: string;
  snapshot: Snapshot;
}

export interface NetworkState {
  scenarioId: string;
  seed: number;
  scenarioEvents: Event[]; // the scenario's scripted events, e.g. the primary-uplink failure
  topology: Topology;
  flows: Flow[];
  eventHistory: Event[];
  leftPanel: PanelState;
  rightPanel: PanelState;
  selectedFlowId: string | null;
  inFlight: boolean;
  error: string | null;
  lastGoodSnapshots: {
    left: Snapshot;
    right: Snapshot;
  };
}

export type NetworkAction =
  | {
      type: 'INIT_SCENARIO';
      payload: {
        scenarioId: string;
        seed: number;
        scenarioEvents: Event[];
        topology: Topology;
        flows: Flow[];
        left: PanelState;
        right: PanelState;
      };
    }
  | { type: 'SET_BASELINE_POLICY'; payload: BaselinePolicy }
  | {
      type: 'REPLAY_BASELINE_SUCCESS';
      payload: {
        policy: BaselinePolicy;
        runId: string;
        snapshot: Snapshot;
      };
    }
  | { type: 'SET_IN_FLIGHT'; payload: boolean }
  | {
      type: 'APPLY_EVENT_SUCCESS';
      payload: {
        event: Event;
        leftSnapshot: Snapshot;
        rightSnapshot: Snapshot;
      };
    }
  | { type: 'APPLY_EVENT_FAILURE'; payload: { error: string } }
  | { type: 'CLEAR_ERROR' }
  | { type: 'SELECT_FLOW'; payload: string | null }
  | { type: 'RESET' | 'SHOW_SNAPSHOTS'; payload: { left: Snapshot; right: Snapshot } };

// Shown until the API answers: no network, no traffic, nothing claimed.
export const EMPTY_SNAPSHOT: Snapshot = {
  step: 0,
  link_state: {},
  allocation: { results: {}, arc_load: {} },
  metrics: {
    dr: 0,
    dr_by_class: {},
    dr_reach: 0,
    unserved_by_cause: {},
    overloaded_arcs: 0,
    overload_excess: 0,
    max_util: 0,
    mean_util: 0,
    arcs_above_90: 0,
    link_util: {},
    latency_stretch: 0,
    recovery_ratio: null,
    churn_flows: 0,
    churn_rate: 0,
    p0_greedy_gap: 0,
    compute_ms: 0,
  },
  affected_flows: [],
  decisions: [],
};

export const initialNetworkState: NetworkState = {
  scenarioId: '',
  seed: 0,
  scenarioEvents: [],
  topology: { nodes: [], links: [] },
  flows: [],
  eventHistory: [],
  leftPanel: { policy: 'S0-QoS', runId: '', snapshot: EMPTY_SNAPSHOT },
  rightPanel: { policy: 'S2', runId: '', snapshot: EMPTY_SNAPSHOT },
  selectedFlowId: null,
  inFlight: false,
  error: null,
  lastGoodSnapshots: { left: EMPTY_SNAPSHOT, right: EMPTY_SNAPSHOT },
};

export function networkReducer(state: NetworkState, action: NetworkAction): NetworkState {
  switch (action.type) {
    case 'INIT_SCENARIO': {
      const { scenarioId, seed, scenarioEvents, topology, flows, left, right } = action.payload;
      return {
        ...state,
        scenarioId,
        seed,
        scenarioEvents,
        topology,
        flows,
        eventHistory: [],
        selectedFlowId: null,
        leftPanel: left,
        rightPanel: right,
        lastGoodSnapshots: { left: left.snapshot, right: right.snapshot },
        error: null,
        inFlight: false,
      };
    }

    case 'SET_BASELINE_POLICY': {
      return {
        ...state,
        leftPanel: {
          ...state.leftPanel,
          policy: action.payload,
        },
      };
    }

    case 'REPLAY_BASELINE_SUCCESS': {
      const { policy, runId, snapshot } = action.payload;
      if (snapshot.step !== state.rightPanel.snapshot.step) {
        return {
          ...state,
          error: `Step mismatch on replay: baseline is at step ${snapshot.step} while right panel is at step ${state.rightPanel.snapshot.step}`,
          inFlight: false,
        };
      }
      return {
        ...state,
        leftPanel: {
          policy,
          runId,
          snapshot,
        },
        lastGoodSnapshots: {
          ...state.lastGoodSnapshots,
          left: snapshot,
        },
        error: null,
        inFlight: false,
      };
    }

    case 'SET_IN_FLIGHT': {
      return {
        ...state,
        inFlight: action.payload,
      };
    }

    case 'APPLY_EVENT_SUCCESS': {
      const { event, leftSnapshot, rightSnapshot } = action.payload;

      // Check step mismatch (Task 3.1)
      if (leftSnapshot.step !== rightSnapshot.step) {
        return {
          ...state,
          error: `Step mismatch: left panel is at step ${leftSnapshot.step} while right panel is at step ${rightSnapshot.step}`,
          inFlight: false,
        };
      }

      return {
        ...state,
        eventHistory: [...state.eventHistory, event],
        leftPanel: {
          ...state.leftPanel,
          snapshot: leftSnapshot,
        },
        rightPanel: {
          ...state.rightPanel,
          snapshot: rightSnapshot,
        },
        lastGoodSnapshots: {
          left: leftSnapshot,
          right: rightSnapshot,
        },
        error: null,
        inFlight: false,
      };
    }

    case 'APPLY_EVENT_FAILURE': {
      // Retain last good snapshots and show error banner
      return {
        ...state,
        error: action.payload.error,
        leftPanel: {
          ...state.leftPanel,
          snapshot: state.lastGoodSnapshots.left,
        },
        rightPanel: {
          ...state.rightPanel,
          snapshot: state.lastGoodSnapshots.right,
        },
        inFlight: false,
      };
    }

    case 'CLEAR_ERROR': {
      return {
        ...state,
        error: null,
      };
    }

    case 'SELECT_FLOW': {
      return {
        ...state,
        selectedFlowId: action.payload,
      };
    }

    case 'RESET':
    case 'SHOW_SNAPSHOTS': {
      const { left, right } = action.payload;
      return {
        ...state,
        eventHistory: [],
        leftPanel: { ...state.leftPanel, snapshot: left },
        rightPanel: { ...state.rightPanel, snapshot: right },
        lastGoodSnapshots: { left, right },
        error: null,
        inFlight: false,
      };
    }

    default:
      return state;
  }
}

interface NetworkContextValue {
  state: NetworkState;
  dispatch: React.Dispatch<NetworkAction>;
}

const NetworkContext = createContext<NetworkContextValue | undefined>(undefined);

export const NetworkProvider: React.FC<{ children: ReactNode; initialState?: NetworkState }> = ({
  children,
  initialState = initialNetworkState,
}) => {
  const [state, dispatch] = useReducer(networkReducer, initialState);

  return (
    <NetworkContext.Provider value={{ state, dispatch }}>
      {children}
    </NetworkContext.Provider>
  );
};

export function useNetwork(): NetworkContextValue {
  const context = useContext(NetworkContext);
  if (!context) {
    throw new Error('useNetwork must be used within a NetworkProvider');
  }
  return context;
}
