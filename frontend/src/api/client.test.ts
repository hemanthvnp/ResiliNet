import { describe, it, expect } from 'vitest';
import { apiClient } from './client';

describe('API Client Mock & Live Compatibility (Task 1.5)', () => {
  it('fetches a valid mocked snapshot matching contract types', async () => {
    const { run_id, snapshot } = await apiClient.createRun({ policy: 'S2', seed: 42 });

    expect(run_id).toBeDefined();
    expect(snapshot).toBeDefined();
    expect(snapshot.step).toBe(0);
    expect(snapshot.metrics).toBeDefined();
    expect(snapshot.metrics.dr).toBe(1.0);
    expect(snapshot.metrics.overloaded_arcs).toBe(0);
    expect(snapshot.allocation.results['F01']).toBeDefined();
  });

  it('correctly simulates failure event transition for S2 vs S0-QoS', async () => {
    // S2 reroutes with 0 overloads
    const s2Snapshot = await apiClient.applyEvent('run-s2-1', { kind: 'fail', links: ['L_DC_PRI'] }, 'S2');
    expect(s2Snapshot.link_state['L_DC_PRI']).toBe('down');
    expect(s2Snapshot.metrics.overloaded_arcs).toBe(0);

    // S0-QoS causes overload violation (> 1.0)
    const s0Snapshot = await apiClient.applyEvent('run-s0-1', { kind: 'fail', links: ['L_DC_PRI'] }, 'S0-QoS');
    expect(s0Snapshot.link_state['L_DC_PRI']).toBe('down');
    expect(s0Snapshot.metrics.overloaded_arcs).toBeGreaterThan(0);
    expect(s0Snapshot.metrics.max_util).toBeGreaterThan(1.0);
  });
});
