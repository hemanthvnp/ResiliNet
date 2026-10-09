import { describe, it, expect } from 'vitest';
import { getDeterministicPositions, getEdgeElements, getLinkColor, getLinkLineStyle } from './TopologyGraph';
import { CAMPUS_TOPOLOGY, MOCK_STEP1_S2_SNAPSHOT } from '../fixtures/mockData';
import { Topology } from '../types/contract';

// Node ids and types of B's campus template (fixtures/topologies/campus.json on main).
// ponytail: inline until this branch is rebased onto main; then import the fixture itself.
const node = (id: string, type: string) => ({ id, type, name: id });
const campusTemplate: Topology = {
  nodes: [
    node('C1', 'core'), node('C2', 'core'), node('AUTH', 'service'), node('EMRG', 'service'),
    node('LMS', 'service'), node('INET', 'service'), node('D1', 'distribution'), node('D2', 'distribution'),
    node('B1', 'building'), node('B2', 'building'), node('B3', 'building'), node('B4', 'building'),
    node('B5', 'building'), node('H1', 'hostel'), node('H2', 'hostel'),
  ],
  links: [],
};
const diamond: Topology = { nodes: ['A', 'B', 'C', 'D'].map((id) => node(id, 'switch')), links: [] };

describe('Deterministic Topology Layout (Task 1.4 & Task 2.2)', () => {
  it('computes identical, deterministic coordinates for the same topology across multiple runs', () => {
    const run1 = getDeterministicPositions(CAMPUS_TOPOLOGY);
    const run2 = getDeterministicPositions(CAMPUS_TOPOLOGY);

    expect(run1).toEqual(run2);
  });

  it("lays out B's campus template in rows: services, core, distribution, then buildings and hostels", () => {
    const pos = getDeterministicPositions(campusTemplate);
    const rowOf = (id: string) => pos[id].y;

    expect(Object.keys(pos)).toHaveLength(15);
    expect(rowOf('AUTH')).toBeLessThan(rowOf('C1'));
    expect(rowOf('C1')).toBe(rowOf('C2'));
    expect(rowOf('C1')).toBeLessThan(rowOf('D1'));
    expect(rowOf('D1')).toBeLessThan(rowOf('B1'));
    expect(rowOf('B1')).toBe(rowOf(campusTemplate.nodes.find((n) => n.type === 'hostel')!.id));
    // no two nodes on the same spot
    expect(new Set(Object.values(pos).map((p) => `${p.x},${p.y}`)).size).toBe(15);
  });

  it('draws a single-row topology such as the diamond on a circle', () => {
    const pos = getDeterministicPositions(diamond);
    expect(new Set(Object.values(pos).map((p) => p.y)).size).toBeGreaterThan(1);
  });

  it('colours edges according to utilization rules (Task 2.2)', () => {
    // 0.2 maps near the green end (high G component, lower R component)
    const color02 = getLinkColor(0.2, false);
    const r02 = parseInt(color02.slice(1, 3), 16);
    const g02 = parseInt(color02.slice(3, 5), 16);
    expect(g02).toBeGreaterThan(r02);

    // 0.95 maps near the red end (high R component, lower G component)
    const color095 = getLinkColor(0.95, false);
    const r095 = parseInt(color095.slice(1, 3), 16);
    const g095 = parseInt(color095.slice(3, 5), 16);
    expect(r095).toBeGreaterThan(g095);

    // 2.5 gets the overload colour (#d946ef)
    const overloadColor = getLinkColor(2.5, false);
    expect(overloadColor).toBe('#d946ef');

    // A down link is red (#ef4444) and dashed whatever its utilization
    expect(getLinkColor(0.0, true)).toBe('#ef4444');
    expect(getLinkColor(0.9, true)).toBe('#ef4444');
    expect(getLinkColor(2.5, true)).toBe('#ef4444');

    expect(getLinkLineStyle(true)).toBe('dashed');
    expect(getLinkLineStyle(false)).toBe('solid');
  });
});

describe('Selected flow route highlight (Task 4.1)', () => {
  it('highlights every link of a two-path flow and no other link', () => {
    // F03 in the S2 step-1 fixture is split over two paths:
    // CS_ENG-DIST_N-CORE2-DC and CS_ENG-DIST_N-DIST_S-CORE2-DC
    const arcs = MOCK_STEP1_S2_SNAPSHOT.allocation.results['F03'].paths.flatMap((p) => p.arcs);
    const edges = getEdgeElements(CAMPUS_TOPOLOGY, MOCK_STEP1_S2_SNAPSHOT, arcs, '#60a5fa');
    const colourOf = (id: string) => edges.find((e) => e.data.id === id)!.data.color;

    for (const id of ['L_CS_DIST', 'L_DIST_N_C2', 'L_DC_BCK', 'L_X_DIST', 'L_DIST_S_C2']) {
      expect(colourOf(id)).toBe('#60a5fa');
    }
    expect(colourOf('L_DC_PRI')).not.toBe('#60a5fa');
    expect(colourOf('L_HST_DIST')).not.toBe('#60a5fa');
  });
});
