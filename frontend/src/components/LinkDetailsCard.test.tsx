import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { LinkDetailsCard, formatSpeed } from './LinkDetailsCard';
import { CAMPUS_TOPOLOGY, MOCK_STEP0_SNAPSHOT } from '../fixtures/mockData';

describe('LinkDetailsCard Component', () => {
  it('formats link speeds correctly in Mbps and Gbps', () => {
    expect(formatSpeed(500)).toBe('500 Mbps');
    expect(formatSpeed(1000)).toBe('1 Gbps (1000 Mbps)');
    expect(formatSpeed(2000)).toBe('2 Gbps (2000 Mbps)');
    expect(formatSpeed(2500)).toBe('2.5 Gbps (2500 Mbps)');
  });

  it('renders link capacity, endpoints and utilization for a selected link', () => {
    const onToggle = vi.fn();
    const onClose = vi.fn();

    render(
      <LinkDetailsCard
        linkId="L_DC_PRI"
        topology={CAMPUS_TOPOLOGY}
        baselineSnapshot={MOCK_STEP0_SNAPSHOT}
        s2Snapshot={MOCK_STEP0_SNAPSHOT}
        baselinePolicy="S0-QoS"
        onToggleStatus={onToggle}
        onClose={onClose}
      />,
    );

    expect(screen.getByTestId('link-details-card')).toBeInTheDocument();
    expect(screen.getByText('L_DC_PRI')).toBeInTheDocument();
    expect(screen.getByTestId('link-capacity-value')).toHaveTextContent(/1.5 Gbps/i);
    expect(screen.getByTestId('s2-used-value')).toBeInTheDocument();
    expect(screen.getByTestId('baseline-used-value')).toBeInTheDocument();
  });

  it('calls onToggleStatus and onClose when buttons are clicked', () => {
    const onToggle = vi.fn();
    const onClose = vi.fn();

    render(
      <LinkDetailsCard
        linkId="L_DC_PRI"
        topology={CAMPUS_TOPOLOGY}
        baselineSnapshot={MOCK_STEP0_SNAPSHOT}
        s2Snapshot={MOCK_STEP0_SNAPSHOT}
        baselinePolicy="S0-QoS"
        onToggleStatus={onToggle}
        onClose={onClose}
      />,
    );

    fireEvent.click(screen.getByTestId('link-toggle-btn'));
    expect(onToggle).toHaveBeenCalledWith('L_DC_PRI', 'up');

    fireEvent.click(screen.getByTestId('link-details-close'));
    expect(onClose).toHaveBeenCalled();
  });
});
