import React, { createContext, useContext, useReducer, ReactNode } from 'react';
import { Topology, Flow, Snapshot, Event } from '../types/contract';
import { CAMPUS_TOPOLOGY, INITIAL_FLOWS, MOCK_STEP0_SNAPSHOT } from '../fixtures/mockData';

export type BaselinePolicy = 'S0-QoS' | 'S0';

export interface PanelState {
  policy: string;
  runId: string;
  snapshot: Snapshot;
}

export interface NetworkState {
  seed: number;
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
        seed: number;
        topology: Topology;
        flows: Flow[];
        initialSnapshot: Snapshot;
      };
    }
  | { type: 'SET_BASELINE_POLICY'; payload: BaselinePolicy }
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
  | { type: 'RESET'; payload: { step0Snapshot: Snapshot } };

export const initialNetworkState: NetworkState = {
  seed: 42,
  topology: CAMPUS_TOPOLOGY,
  flows: INITIAL_FLOWS,
  eventHistory: [],
  leftPanel: {
    policy: 'S0-QoS',
    runId: 'run-s0-qos-init',
    snapshot: MOCK_STEP0_SNAPSHOT,
  },
  rightPanel: {
    policy: 'S2',
    runId: 'run-s2-init',
    snapshot: MOCK_STEP0_SNAPSHOT,
  },
  selectedFlowId: 'F03',
  inFlight: false,
  error: null,
  lastGoodSnapshots: {
    left: MOCK_STEP0_SNAPSHOT,
    right: MOCK_STEP0_SNAPSHOT,
  },
};

export function networkReducer(state: NetworkState, action: NetworkAction): NetworkState {
  switch (action.type) {
    case 'INIT_SCENARIO': {
      const { seed, topology, flows, initialSnapshot } = action.payload;
      return {
        ...state,
        seed,
        topology,
        flows,
        eventHistory: [],
        leftPanel: {
          ...state.leftPanel,
          snapshot: initialSnapshot,
        },
        rightPanel: {
          ...state.rightPanel,
          snapshot: initialSnapshot,
        },
        lastGoodSnapshots: {
          left: initialSnapshot,
          right: initialSnapshot,
        },
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

    case 'SET_IN_FLIGHT': {
      return {
        ...state,
        inFlight: action.payload,
      };
    }

    case 'APPLY_EVENT_SUCCESS': {
      const { event, leftSnapshot, rightSnapshot } = action.payload;
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

    case 'RESET': {
      const { step0Snapshot } = action.payload;
      return {
        ...state,
        eventHistory: [],
        leftPanel: {
          ...state.leftPanel,
          snapshot: step0Snapshot,
        },
        rightPanel: {
          ...state.rightPanel,
          snapshot: step0Snapshot,
        },
        lastGoodSnapshots: {
          left: step0Snapshot,
          right: step0Snapshot,
        },
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
