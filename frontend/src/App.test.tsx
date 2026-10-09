import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import App from './App';
import { apiClient } from './api/client';
import { MOCK_STEP1_S2_SNAPSHOT, MOCK_STEP1_S0_QOS_SNAPSHOT } from './fixtures/mockData';

// Cytoscape mock for jsdom
vi.mock('cytoscape', () => {
  return {
    default: vi.fn(() => {
      // simulate tap handler on edges
      return {
        on: vi.fn((event, selector, handler) => {
          if (event === 'tap' && selector === 'edge') {
            (global as any).__mockCytoscapeTapEdge = handler;
          }
        }),
        destroy: vi.fn(),
        elements: vi.fn(() => ({
          style: vi.fn(),
        })),
      };
    }),
  };
});

describe('App Component (Phase 1 & Phase 2)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders the ResiliNet application header and main dashboard (Task 1.2)', async () => {
    const { findByText, findByTestId } = render(<App />);

    expect(await findByText('ResiliNet')).toBeInTheDocument();
    expect(await findByText(/Campus Network Rerouter/i)).toBeInTheDocument();
    expect(await findByTestId('app-root')).toBeInTheDocument();
    expect(await findByTestId('baseline-panel')).toBeInTheDocument();
    expect(await findByTestId('s2-panel')).toBeInTheDocument();
    expect(await findByTestId('flow-table')).toBeInTheDocument();
  });

  it('handles link failure event and updates both panels (Task 2.3 & Task 2.6)', async () => {
    const applyEventSpy = vi.spyOn(apiClient, 'applyEvent');
    applyEventSpy.mockImplementation(async (_runId, _event, policy) => {
      if (policy === 'S2') return MOCK_STEP1_S2_SNAPSHOT;
      return MOCK_STEP1_S0_QOS_SNAPSHOT;
    });

    render(<App />);

    await waitFor(() => {
      expect((global as any).__mockCytoscapeTapEdge).toBeDefined();
    });

    // Simulate clicking link L_DC_PRI
    const mockEvent = {
      target: {
        id: () => 'L_DC_PRI',
      },
    };

    await waitFor(async () => {
      (global as any).__mockCytoscapeTapEdge(mockEvent);
    });

    await waitFor(() => {
      expect(applyEventSpy).toHaveBeenCalled();
    });

    // Verify step incremented and post-failure state reflected
    await waitFor(() => {
      expect(screen.getByText('Post-Failure (Overloaded)')).toBeInTheDocument();
    });
  });

  it('displays error banner on request failure while retaining snapshots (Task 2.5)', async () => {
    const applyEventSpy = vi.spyOn(apiClient, 'applyEvent');
    applyEventSpy.mockRejectedValueOnce(new Error('Simulated backend timeout'));

    render(<App />);

    await waitFor(() => {
      expect((global as any).__mockCytoscapeTapEdge).toBeDefined();
    });

    const mockEvent = {
      target: {
        id: () => 'L_CORE_INTER',
      },
    };

    await waitFor(async () => {
      (global as any).__mockCytoscapeTapEdge(mockEvent);
    });

    // Expect error banner to appear
    expect(await screen.findByTestId('error-banner')).toBeInTheDocument();
    expect(screen.getByText(/Simulated backend timeout/i)).toBeInTheDocument();

    // Verify last good snapshot is still displayed
    expect(screen.getByTestId('baseline-panel')).toBeInTheDocument();

    // Dismiss error
    fireEvent.click(screen.getByText('Dismiss'));
    await waitFor(() => {
      expect(screen.queryByTestId('error-banner')).not.toBeInTheDocument();
    });
  });

  it('defaults baseline selector to S0-QoS and switches layout modes (Task 3.3 & Task 3.5)', async () => {
    render(<App />);

    // Baseline selector should default to S0-QoS
    const selector = await screen.findByTestId('baseline-selector') as HTMLSelectElement;
    expect(selector.value).toBe('S0-QoS');

    // Layout switcher should toggle between side-by-side, stacked, and toggle
    const stackedBtn = screen.getByText('Stacked');
    fireEvent.click(stackedBtn);
    expect(stackedBtn).toHaveClass('layout-btn-active');

    const toggleBtn = screen.getByText('Toggle');
    fireEvent.click(toggleBtn);
    expect(toggleBtn).toHaveClass('layout-btn-active');
    expect(screen.getByTestId('toggle-policy-bar')).toBeInTheDocument();
  });

  it('replays event history when baseline policy is switched (Task 3.3)', async () => {
    const createRunSpy = vi.spyOn(apiClient, 'createRun');
    const applyEventSpy = vi.spyOn(apiClient, 'applyEvent');

    render(<App />);

    await waitFor(() => {
      expect((global as any).__mockCytoscapeTapEdge).toBeDefined();
    });

    // 1. Simulate first failure event
    const mockEvent = { target: { id: () => 'L_DC_PRI' } };
    await waitFor(async () => {
      (global as any).__mockCytoscapeTapEdge(mockEvent);
    });

    await waitFor(() => {
      expect(applyEventSpy).toHaveBeenCalled();
    });

    // 2. Now switch baseline to S0
    const selector = screen.getByTestId('baseline-selector');
    fireEvent.change(selector, { target: { value: 'S0' } });

    // Should create new run for S0 and replay the event
    await waitFor(() => {
      expect(createRunSpy).toHaveBeenCalledWith(expect.objectContaining({ policy: 'S0' }));
    });
  });
});
