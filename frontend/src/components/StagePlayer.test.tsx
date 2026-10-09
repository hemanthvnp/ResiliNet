import { describe, it, expect } from 'vitest';
import { changedLinks, stageCaption, stageSnapshot } from './StagePlayer';
import { MOCK_STEP0_SNAPSHOT, MOCK_STEP1_S0_QOS_SNAPSHOT, MOCK_STEP1_S2_SNAPSHOT, CAMPUS_TOPOLOGY } from '../fixtures/mockData';

const before = { left: MOCK_STEP0_SNAPSHOT, right: MOCK_STEP0_SNAPSHOT };
const after = { left: MOCK_STEP1_S0_QOS_SNAPSHOT, right: MOCK_STEP1_S2_SNAPSHOT };
const names = { left: 'S0-QoS', right: 'S2' };

describe('Stage player (Task 5.6)', () => {
  it('shows the previous step, then the old routes with the new link states, then the current step', () => {
    expect(stageSnapshot(0, MOCK_STEP0_SNAPSHOT, MOCK_STEP1_S2_SNAPSHOT)).toBe(MOCK_STEP0_SNAPSHOT);

    const fails = stageSnapshot(1, MOCK_STEP0_SNAPSHOT, MOCK_STEP1_S2_SNAPSHOT);
    expect(fails.allocation).toBe(MOCK_STEP0_SNAPSHOT.allocation); // routes not yet recomputed
    expect(fails.link_state).toBe(MOCK_STEP1_S2_SNAPSHOT.link_state); // the link is already down
    expect(fails.step).toBe(MOCK_STEP1_S2_SNAPSHOT.step);

    expect(stageSnapshot(2, MOCK_STEP0_SNAPSHOT, MOCK_STEP1_S2_SNAPSHOT)).toBe(MOCK_STEP1_S2_SNAPSHOT);
  });

  it('finds the failed link from the two steps', () => {
    expect(changedLinks(MOCK_STEP0_SNAPSHOT, MOCK_STEP1_S2_SNAPSHOT)).toEqual({ failed: ['L_DC_PRI'], recovered: [] });
    expect(changedLinks(MOCK_STEP1_S2_SNAPSHOT, MOCK_STEP0_SNAPSHOT)).toEqual({ failed: [], recovered: ['L_DC_PRI'] });
  });

  it('captions each stage from the snapshots', () => {
    const pct = (v: number) => `${(v * 100).toFixed(1)}%`;
    expect(stageCaption(0, before, after, names, CAMPUS_TOPOLOGY)).toBe(
      `Before: S0-QoS delivers ${pct(MOCK_STEP0_SNAPSHOT.metrics.dr)}, S2 delivers ${pct(MOCK_STEP0_SNAPSHOT.metrics.dr)}.`,
    );

    const affected = new Set([...MOCK_STEP1_S0_QOS_SNAPSHOT.affected_flows, ...MOCK_STEP1_S2_SNAPSHOT.affected_flows]).size;
    const fails = stageCaption(1, before, after, names, CAMPUS_TOPOLOGY);
    expect(fails).toContain('L_DC_PRI (');
    expect(fails).toContain(`fails: ${affected} flows were using it (marked red)`);

    const rerouted = stageCaption(2, before, after, names, CAMPUS_TOPOLOGY);
    expect(rerouted).toContain(`S0-QoS: ${pct(MOCK_STEP1_S0_QOS_SNAPSHOT.metrics.dr)} delivered`);
    expect(rerouted).toContain(`S2: ${pct(MOCK_STEP1_S2_SNAPSHOT.metrics.dr)} delivered`);
    expect(rerouted).toContain(MOCK_STEP1_S2_SNAPSHOT.metrics.overloaded_arcs === 0 ? 'no link overloaded' : 'overloaded link');
  });

  it('says a link recovers when the event recovered it', () => {
    expect(stageCaption(1, after, before, names, CAMPUS_TOPOLOGY)).toMatch(/^L_DC_PRI \(.*\) recovers\.$/);
  });
});
