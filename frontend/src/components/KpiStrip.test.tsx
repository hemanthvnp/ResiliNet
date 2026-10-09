import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { KpiStrip, CAUSE_DISPLAY_ORDER } from './KpiStrip';
import { MOCK_STEP1_S0_QOS_SNAPSHOT, MOCK_STEP1_S2_SNAPSHOT } from '../fixtures/mockData';

describe('KPI Strip Component (Task 3.4)', () => {
  it('displays accurate snapshot metrics for baseline panel with overloads', () => {
    render(
      <KpiStrip
        metrics={MOCK_STEP1_S0_QOS_SNAPSHOT.metrics}
        policyName="S0-QoS"
        label="Post-Failure"
      />
    );

    expect(screen.getByText('S0-QoS')).toBeInTheDocument();
    expect(screen.getByText('65.0%')).toBeInTheDocument(); // DR
    expect(screen.getByText('100.0%')).toBeInTheDocument(); // P0
    expect(screen.getByText('55.0%')).toBeInTheDocument(); // P1
    expect(screen.getByText('175%')).toBeInTheDocument(); // Max Util (overload)
    expect(screen.getByText('1')).toBeInTheDocument(); // 1 overloaded link
  });

  it('displays accurate snapshot metrics for S2 resilient panel with 0 overloads', () => {
    render(
      <KpiStrip
        metrics={MOCK_STEP1_S2_SNAPSHOT.metrics}
        policyName="S2-Resilient"
        label="Capacity Protected"
      />
    );

    expect(screen.getByText('S2-Resilient')).toBeInTheDocument();
    expect(screen.getByText('98.0%')).toBeInTheDocument(); // DR
    expect(screen.getAllByText('100.0%').length).toBeGreaterThanOrEqual(1); // P0 and P1
    expect(screen.getByText('0')).toBeInTheDocument(); // 0 overloaded links
  });

  it('displays unserved traffic breakdown in the fixed required order (Task 3.4)', () => {
    render(
      <KpiStrip
        metrics={MOCK_STEP1_S0_QOS_SNAPSHOT.metrics}
        policyName="S0-QoS"
      />
    );

    const causeElements = screen.getByTestId('unserved-causes');
    expect(causeElements).toBeInTheDocument();

    // Verify all 4 required causes exist in the fixed order
    CAUSE_DISPLAY_ORDER.forEach((cause) => {
      expect(screen.getByTestId(`cause-${cause}`)).toBeInTheDocument();
    });

    // Check OVERLOAD_LOSS value
    expect(screen.getByTestId('cause-OVERLOAD_LOSS')).toHaveTextContent('770 Mbps');
  });
});
