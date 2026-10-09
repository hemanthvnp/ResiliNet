import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DecisionPanel } from './DecisionPanel';
import { DecisionRecord } from '../types/contract';

// PLAN.md section 10 decision log, copied by hand
const F12: DecisionRecord = {
  flow_id: 'F12', cls: 0, demand: 15, step: 2,
  failed_links: ['L7'],
  previous: [{ arcs: ['L2:A>B', 'L7:B>D'], rate: 10 }],
  reference_path: ['L2:A>B', 'L7:B>D'],
  reference_status: 'INVALID: L7 down',
  attempts: [{ iter: 1, arcs: ['L5:A>C', 'L6:C>D'], cost: 4, latency: 4, bottleneck: 10, pushed: 10 }],
  delivered: 10.0, unserved: 5.0, cause: 'INSUFFICIENT_CAPACITY',
  cut: [
    { arc: 'L5:A>C', state: 'saturated', load_by_class: { 0: 10 } },
    { arc: 'L7:B>D', state: 'down', load_by_class: {} },
  ],
  maxflow_bound: 10, greedy_gap: 0.0,
  explanation:
    'F12 (P0, 15 Mbps): path A-B-D invalid (L7 down). Moved 10 Mbps to A-C-D (latency 4 ms). 5 Mbps unserved: cut L5 saturated by P0 (10 Mbps).',
};

describe('DecisionPanel (Task 4.2)', () => {
  it('shows the section 10 explanation unchanged, with attempts, cut and bounds', () => {
    render(<DecisionPanel decision={F12} />);
    expect(screen.getByText(F12.explanation)).toBeInTheDocument();
    expect(screen.getByText('Cause: INSUFFICIENT_CAPACITY')).toBeInTheDocument();
    expect(screen.getByText('L5:A>C, L6:C>D')).toBeInTheDocument();
    expect(screen.getByText('Cut L5:A>C: saturated · P0 10 Mbps')).toBeInTheDocument();
    expect(screen.getByText('Cut L7:B>D: down')).toBeInTheDocument();
    expect(screen.getByText('Max-flow bound: 10')).toBeInTheDocument();
    expect(screen.getByText('Greedy gap: 0')).toBeInTheDocument();
  });

  it('shows a DISCONNECTED flow as physically disconnected', () => {
    render(
      <DecisionPanel
        decision={{
          ...F12,
          cause: 'DISCONNECTED', attempts: [], cut: [], delivered: 0, unserved: 15,
          maxflow_bound: 0, greedy_gap: null,
          explanation: 'F12 (P0, 15 Mbps): no path from A to D. 15 Mbps unserved.',
        }}
      />,
    );
    expect(screen.getByText(/Physically disconnected/)).toBeInTheDocument();
    expect(screen.getByText('Greedy gap: —')).toBeInTheDocument();
  });
});
