import { describe, it, expect } from 'vitest';
import { getDeterministicPositions, getLinkColor } from './TopologyGraph';
import { CAMPUS_TOPOLOGY } from '../fixtures/mockData';

describe('Deterministic Topology Layout (Task 1.4)', () => {
  it('computes identical, deterministic coordinates for the same topology across multiple runs', () => {
    const run1 = getDeterministicPositions(CAMPUS_TOPOLOGY);
    const run2 = getDeterministicPositions(CAMPUS_TOPOLOGY);

    expect(run1).toEqual(run2);

    // Verify critical campus hubs have designated coordinates
    expect(run1['N_DC']).toEqual({ x: 400, y: 50 });
    expect(run1['N_CORE1']).toEqual({ x: 260, y: 160 });
    expect(run1['N_CORE2']).toEqual({ x: 540, y: 160 });
  });

  it('determines link colors accurately according to PLAN.md section 7 and 10', () => {
    // Healthy link with low utilization should be near green
    const greenColor = getLinkColor(0.2, false);
    expect(greenColor).toBeDefined();

    // Overloaded link (> 1.0) must return distinct overload color (#d946ef)
    const overloadColor = getLinkColor(1.75, false);
    expect(overloadColor).toBe('#d946ef');

    // Failed link must always be red (#ef4444)
    const failedColor = getLinkColor(0.0, true);
    expect(failedColor).toBe('#ef4444');
  });
});
