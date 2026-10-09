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

  it("completes a baseline's explanation with the route it took and what arrived", () => {
    // S0-QoS on 02_uplink_failure after L6 fails: the record stops at the invalid path
    const record = {
      ...F12,
      flow_id: 'F2', cls: 1, demand: 10, attempts: [], cut: [], maxflow_bound: null, greedy_gap: null,
      cause: 'OVERLOAD_LOSS' as const, delivered: 6.67, unserved: 3.33,
      explanation: 'F2 (P1, 10 Mbps): path B1-D1-C1-LMS invalid (L6 down).',
    };
    const result = {
      flow_id: 'F2', cause: 'OVERLOAD_LOSS' as const, delivered: 6.666666, unserved: 3.333334,
      paths: [{ arcs: ['L10:B1>D1', 'L7:D1>C2', 'L1:C2>C1', 'L3:C1>LMS'], rate: 10 }],
    };
    render(<DecisionPanel decision={record} result={result} />);

    expect(screen.getByTestId('baseline-route')).toHaveTextContent(
      'Routed on B1-D1-C2-C1-LMS with no capacity check: 6.67 of 10 Mbps delivered.', // the loss is already in the explanation
    );
  });

  it('adds no route line to an S2 record, which explains its own attempts', () => {
    const result = { flow_id: F12.flow_id, cause: 'NONE' as const, delivered: 1, unserved: 0, paths: [{ arcs: ['L1:A>B'], rate: 1 }] };
    render(<DecisionPanel decision={F12} result={result} />);
    expect(screen.queryByTestId('baseline-route')).not.toBeInTheDocument();
  });
});
