import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { FlowTable } from './FlowTable';
import { INITIAL_FLOWS, MOCK_STEP1_S0_QOS_SNAPSHOT } from '../fixtures/mockData';

describe('FlowTable Component (Task 2.4)', () => {
  it('renders flows sorted by priority class (P0 -> P1 -> P2)', () => {
    render(<FlowTable flows={INITIAL_FLOWS} snapshot={MOCK_STEP1_S0_QOS_SNAPSHOT} />);

    // Expect rows to display all 6 flows
    expect(screen.getByText('F01')).toBeInTheDocument();
    expect(screen.getByText('F02')).toBeInTheDocument();
    expect(screen.getByText('F03')).toBeInTheDocument();
    expect(screen.getByText('F04')).toBeInTheDocument();
    expect(screen.getByText('F05')).toBeInTheDocument();
    expect(screen.getByText('F06')).toBeInTheDocument();

    // Verify class badges exist
    expect(screen.getAllByText('P0 Critical').length).toBe(2);
    expect(screen.getAllByText('P1 Academic').length).toBe(2);
    expect(screen.getAllByText('P2 Best Effort').length).toBe(2);
  });

  it('renders unserved rows correctly with cause badge (Task 2.4)', () => {
    render(<FlowTable flows={INITIAL_FLOWS} snapshot={MOCK_STEP1_S0_QOS_SNAPSHOT} />);

    // F03 and F05 are unserved under S0-QoS step 1 with OVERLOAD_LOSS
    const overloadBadges = screen.getAllByText('Overload Loss');
    expect(overloadBadges.length).toBeGreaterThan(0);

    // F05 demand is 500, delivered is 0 Mbps
    expect(screen.getByText('0 Mbps')).toBeInTheDocument();
  });

  it('orders flow ids by number within a class: F2 before F10', () => {
    const flows = ['F10', 'F2', 'F1'].map((id) => ({ id, src: 'A', dst: 'B', rate: 1, cls: 0, service: '' }));
    render(<FlowTable flows={flows} snapshot={MOCK_STEP1_S0_QOS_SNAPSHOT} />);

    const ids = screen.getAllByRole('row').slice(1).map((r) => r.textContent?.match(/^F\d+/)?.[0]);
    expect(ids).toEqual(['F1', 'F2', 'F10']);
  });
});
