import { describe, it, expect } from 'vitest';
import { networkReducer, initialNetworkState, NetworkState } from './NetworkStore';
import { MOCK_STEP0_SNAPSHOT, MOCK_STEP1_S2_SNAPSHOT, MOCK_STEP1_S0_QOS_SNAPSHOT, CAMPUS_TOPOLOGY, INITIAL_FLOWS } from '../fixtures/mockData';

describe('Network Reducer (Task 2.1)', () => {
  it('handles INIT_SCENARIO properly', () => {
    const nextState = networkReducer({ ...initialNetworkState, selectedFlowId: 'F03' }, {
      type: 'INIT_SCENARIO',
      payload: {
        scenarioId: 'campus-template',
        seed: 99,
        scenarioEvents: [{ step: 1, kind: 'fail', links: ['L_DC_PRI'] }],
        topology: CAMPUS_TOPOLOGY,
        flows: INITIAL_FLOWS,
        left: { policy: 'S0-QoS', runId: 'run-left', snapshot: MOCK_STEP0_SNAPSHOT },
        right: { policy: 'S2', runId: 'run-right', snapshot: MOCK_STEP0_SNAPSHOT },
      },
    });

    expect(nextState.seed).toBe(99);
    expect(nextState.scenarioId).toBe('campus-template');
    expect(nextState.topology).toBe(CAMPUS_TOPOLOGY);
    expect([nextState.leftPanel.runId, nextState.rightPanel.runId]).toEqual(['run-left', 'run-right']);
    expect(nextState.eventHistory).toEqual([]);
    expect(nextState.selectedFlowId).toBeNull(); // a flow id from the old scenario must not carry over
    expect(nextState.leftPanel.snapshot.step).toBe(0);
    expect(nextState.rightPanel.snapshot.step).toBe(0);
    expect(nextState.inFlight).toBe(false);
  });

  it('updates baseline policy with SET_BASELINE_POLICY', () => {
    const nextState = networkReducer(initialNetworkState, {
      type: 'SET_BASELINE_POLICY',
      payload: 'S0',
    });

    expect(nextState.leftPanel.policy).toBe('S0');
  });

  it('sets and releases inFlight loading lock', () => {
    const lockedState = networkReducer(initialNetworkState, {
      type: 'SET_IN_FLIGHT',
      payload: true,
    });
    expect(lockedState.inFlight).toBe(true);

    const unlockedState = networkReducer(lockedState, {
      type: 'SET_IN_FLIGHT',
      payload: false,
    });
    expect(unlockedState.inFlight).toBe(false);
  });

  it('commits both snapshots together on APPLY_EVENT_SUCCESS', () => {
    const event = { step: 1, kind: 'fail' as const, links: ['L_DC_PRI'] };
    const nextState = networkReducer(initialNetworkState, {
      type: 'APPLY_EVENT_SUCCESS',
      payload: {
        event,
        leftSnapshot: MOCK_STEP1_S0_QOS_SNAPSHOT,
        rightSnapshot: MOCK_STEP1_S2_SNAPSHOT,
      },
    });

    expect(nextState.eventHistory).toHaveLength(1);
    expect(nextState.eventHistory[0]).toEqual(event);
    expect(nextState.leftPanel.snapshot.step).toBe(1);
    expect(nextState.rightPanel.snapshot.step).toBe(1);
    expect(nextState.leftPanel.snapshot.metrics.overloaded_arcs).toBeGreaterThan(0);
    expect(nextState.rightPanel.snapshot.metrics.overloaded_arcs).toBe(0);
    expect(nextState.inFlight).toBe(false);
  });

  it('detects step mismatch between panels on APPLY_EVENT_SUCCESS (Task 3.1)', () => {
    const event = { step: 1, kind: 'fail' as const, links: ['L_DC_PRI'] };
    const mismatchSnapshot = { ...MOCK_STEP1_S2_SNAPSHOT, step: 2 }; // step 2 vs step 1

    const nextState = networkReducer(initialNetworkState, {
      type: 'APPLY_EVENT_SUCCESS',
      payload: {
        event,
        leftSnapshot: MOCK_STEP1_S0_QOS_SNAPSHOT, // step 1
        rightSnapshot: mismatchSnapshot,         // step 2
      },
    });

    expect(nextState.error).toContain('Step mismatch: left panel is at step 1 while right panel is at step 2');
    expect(nextState.inFlight).toBe(false);
  });

  it('updates baseline policy and snapshot on REPLAY_BASELINE_SUCCESS (Task 3.3)', () => {
    const replayedSnapshot = { ...MOCK_STEP1_S0_QOS_SNAPSHOT, step: 0 };
    const nextState = networkReducer(initialNetworkState, {
      type: 'REPLAY_BASELINE_SUCCESS',
      payload: {
        policy: 'S0',
        runId: 'run-s0-replayed',
        snapshot: replayedSnapshot,
      },
    });

    expect(nextState.leftPanel.policy).toBe('S0');
    expect(nextState.leftPanel.runId).toBe('run-s0-replayed');
    expect(nextState.leftPanel.snapshot).toEqual(replayedSnapshot);
    expect(nextState.error).toBeNull();
  });

  it('retains last good snapshots on APPLY_EVENT_FAILURE (Task 2.5)', () => {
    // Start with a valid state at step 0
    const stateWithGoodSnapshot: NetworkState = {
      ...initialNetworkState,
      inFlight: true,
      lastGoodSnapshots: {
        left: MOCK_STEP0_SNAPSHOT,
        right: MOCK_STEP0_SNAPSHOT,
      },
    };

    const nextState = networkReducer(stateWithGoodSnapshot, {
      type: 'APPLY_EVENT_FAILURE',
      payload: { error: 'Network timeout during event computation' },
    });

    expect(nextState.error).toBe('Network timeout during event computation');
    expect(nextState.inFlight).toBe(false);
    expect(nextState.leftPanel.snapshot).toEqual(MOCK_STEP0_SNAPSHOT);
    expect(nextState.rightPanel.snapshot).toEqual(MOCK_STEP0_SNAPSHOT);
  });

  it('clears error on CLEAR_ERROR', () => {
    const stateWithError = { ...initialNetworkState, error: 'Some error' };
    const nextState = networkReducer(stateWithError, { type: 'CLEAR_ERROR' });
    expect(nextState.error).toBeNull();
  });

  it('updates selected flow on SELECT_FLOW', () => {
    const nextState = networkReducer(initialNetworkState, {
      type: 'SELECT_FLOW',
      payload: 'F01',
    });
    expect(nextState.selectedFlowId).toBe('F01');
  });

  it('resets both panels to step 0 on RESET', () => {
    const stateWithHistory: NetworkState = {
      ...initialNetworkState,
      eventHistory: [{ step: 1, kind: 'fail', links: ['L_DC_PRI'] }],
      leftPanel: { ...initialNetworkState.leftPanel, snapshot: MOCK_STEP1_S0_QOS_SNAPSHOT },
      rightPanel: { ...initialNetworkState.rightPanel, snapshot: MOCK_STEP1_S2_SNAPSHOT },
    };

    const nextState = networkReducer(stateWithHistory, {
      type: 'RESET',
      payload: { left: MOCK_STEP0_SNAPSHOT, right: { ...MOCK_STEP0_SNAPSHOT, metrics: { ...MOCK_STEP0_SNAPSHOT.metrics, dr: 0.5 } } },
    });

    // Each panel gets its own server snapshot, not a shared one
    expect(nextState.leftPanel.snapshot.metrics.dr).toBe(MOCK_STEP0_SNAPSHOT.metrics.dr);
    expect(nextState.rightPanel.snapshot.metrics.dr).toBe(0.5);

    expect(nextState.eventHistory).toEqual([]);
    expect(nextState.leftPanel.snapshot.step).toBe(0);
    expect(nextState.rightPanel.snapshot.step).toBe(0);
  });
});
