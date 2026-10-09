import { describe, it, expect } from 'vitest';
import { flowRatesByLink, getDeterministicPositions, getEdgeElements, getLinkColor, getLinkHint, getLinkLabel, getLinkLineStyle, getNodeLabel } from './TopologyGraph';
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

  it('wraps a wide layer such as 37 generated buildings onto rows of at most 12', () => {
    const wide: Topology = {
      nodes: [node('C1', 'core'), ...Array.from({ length: 37 }, (_, i) => node(`N${100 + i}`, 'building'))],
      links: [],
    };
    const pos = getDeterministicPositions(wide);
    const perRow = new Map<number, number>();
    for (const p of Object.values(pos)) perRow.set(p.y, (perRow.get(p.y) ?? 0) + 1);

    expect(Math.max(...perRow.values())).toBeLessThanOrEqual(12);
    expect(new Set(Object.values(pos).map((p) => `${p.x},${p.y}`)).size).toBe(38);
    expect(Object.entries(pos).every(([id, p]) => id === 'C1' || p.y > pos['C1'].y)).toBe(true);
  });

  it('orders generated ids by number within a row: N2 left of N10', () => {
    const pos = getDeterministicPositions({
      nodes: [node('C1', 'core'), node('N10', 'building'), node('N2', 'building'), node('N3', 'building')],
      links: [],
    });
    expect(pos['N2'].x).toBeLessThan(pos['N3'].x);
    expect(pos['N3'].x).toBeLessThan(pos['N10'].x);
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

  it('labels links so state does not depend on colour alone (Task 5.3)', () => {
    expect(getLinkLabel(0.95, true)).toBe('DOWN'); // a failed link, whatever its last load
    expect(getLinkLabel(1.0, false)).toBe('100%'); // same red as DOWN, told apart by text
    expect(getLinkLabel(2.5, false)).toBe('250%');
    expect(getLinkLabel(0.9, false)).toBe('90%');
    expect(getLinkLabel(0.5, false)).toBe('');
    expect(getLinkLabel(undefined, false)).toBe('');
  });

  it('names every node on the campus template but only the backbone on a large network', () => {
    expect(getNodeLabel({ name: 'Library', type: 'building' }, 15)).toBe('Library');
    expect(getNodeLabel({ name: 'Building 7', type: 'building' }, 50)).toBe('');
    expect(getNodeLabel({ name: 'Hostel 1', type: 'hostel' }, 50)).toBe('');
    expect(getNodeLabel({ name: 'Core 1', type: 'core' }, 50)).toBe('Core 1');
    expect(getNodeLabel({ name: 'Auth server', type: 'service' }, 50)).toBe('Auth server');
    expect(getNodeLabel({ name: 'Distribution 3', type: 'distribution' }, 50)).toBe('Distribution 3');
  });

  it('names the hovered link and what a click will do', () => {
    const topo: Topology = {
      nodes: [node('C1', 'core'), { id: 'D1', type: 'distribution', name: 'Distribution 1' }],
      links: [{ id: 'L6', u: 'C1', v: 'D1', capacity: 20, latency: 1, status: 'up' }],
    };
    const snap = (state: 'up' | 'down') => ({ ...MOCK_STEP1_S2_SNAPSHOT, link_state: { L6: state } });

    expect(getLinkHint(topo, snap('up'), 'L6')).toBe('Click to fail L6: C1 ↔ Distribution 1 (20 Mbps)');
    expect(getLinkHint(topo, snap('down'), 'L6')).toBe('Click to recover L6: C1 ↔ Distribution 1 (20 Mbps)');
    expect(getLinkHint(topo, snap('up'), 'L99')).toBe('');
  });

  it('draws every link at least 3.5 px wide so it is easy to click', () => {
    const edges = getEdgeElements(CAMPUS_TOPOLOGY, MOCK_STEP1_S2_SNAPSHOT, [], '#38bdf8');
    expect(Math.min(...edges.map((e) => e.data.width as number))).toBeGreaterThanOrEqual(3.5);
  });

  describe('flow animation (Task 5.5)', () => {
    // A split flow: 10 Mbps A-B-D and 5 Mbps A-C-D (the PLAN.md section 4 diamond, healthy, under S2)
    const paths = [
      { arcs: ['L2:A>B', 'L7:B>D'], rate: 10 },
      { arcs: ['L5:A>C', 'L6:C>D'], rate: 5 },
    ];
    const diamondTopo: Topology = {
      nodes: ['A', 'B', 'C', 'D'].map((id) => node(id, 'switch')),
      links: [
        { id: 'L2', u: 'A', v: 'B', capacity: 10, latency: 1, status: 'up' },
        { id: 'L7', u: 'B', v: 'D', capacity: 10, latency: 1, status: 'up' },
        { id: 'L5', u: 'A', v: 'C', capacity: 10, latency: 2, status: 'up' },
        { id: 'L6', u: 'C', v: 'D', capacity: 10, latency: 2, status: 'up' },
      ],
    };
    const snap = (util: Record<string, number>) => ({
      ...MOCK_STEP1_S2_SNAPSHOT,
      link_state: { L2: 'up', L7: 'up', L5: 'up', L6: 'up' } as Record<string, 'up' | 'down'>,
      metrics: { ...MOCK_STEP1_S2_SNAPSHOT.metrics, link_util: util },
    });
    const byId = (edges: ReturnType<typeof getEdgeElements>) => Object.fromEntries(edges.map((e) => [e.data.id, e]));

    it('adds up a flow\'s Mbps per link over its paths', () => {
      expect(flowRatesByLink(paths)).toEqual({ L2: 10, L7: 10, L5: 5, L6: 5 });
      expect(flowRatesByLink([{ arcs: ['L1:A>B', 'L2:B>C'], rate: 3 }, { arcs: ['L1:A>B', 'L3:B>C'], rate: 2 }])).toEqual({ L1: 5, L2: 3, L3: 2 });
    });

    it('animates both paths of a split flow, thicker where it carries more', () => {
      const e = byId(getEdgeElements(diamondTopo, snap({ L2: 1, L7: 1, L5: 1, L6: 1 }), [], '#38bdf8', flowRatesByLink(paths)));
      for (const id of ['L2', 'L7', 'L5', 'L6']) expect(e[id].classes).toContain('flowing');
      expect(e.L2.data.width).toBeGreaterThan(e.L5.data.width);
    });

    it('draws a link red only in the panel where it is overloaded', () => {
      const rates = flowRatesByLink(paths);
      const baseline = byId(getEdgeElements(diamondTopo, snap({ L2: 2.5, L7: 2.5, L5: 0, L6: 0 }), [], '#38bdf8', rates));
      const s2 = byId(getEdgeElements(diamondTopo, snap({ L2: 1, L7: 1, L5: 0.5, L6: 0.5 }), [], '#38bdf8', rates));
      expect(baseline.L2.classes).toBe('flowing lossy');
      expect(baseline.L5.classes).toBe('flowing');
      expect(s2.L2.classes).toBe('flowing');
    });

    it('animates nothing when no flow is selected', () => {
      const e = getEdgeElements(diamondTopo, snap({ L2: 1 }), [], '#38bdf8');
      expect(e.every((x) => !x.classes)).toBe(true);
    });
  });
});
