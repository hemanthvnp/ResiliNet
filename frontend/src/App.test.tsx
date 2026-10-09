import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import App from './App';
import { apiClient } from './api/client';
import {
  CAMPUS_TOPOLOGY,
  INITIAL_FLOWS,
  MOCK_STEP0_SNAPSHOT,
  MOCK_STEP1_S2_SNAPSHOT,
  MOCK_STEP1_S0_QOS_SNAPSHOT,
} from './fixtures/mockData';
import { RunResponse } from './types/contract';

// A fake API server: run ids name their policy, the scenario scripts the uplink failure.
function stubApi() {
  vi.spyOn(apiClient, 'getScenarios').mockResolvedValue([
    { id: 'campus-template', name: 'Campus', description: 'test campus' },
  ]);
  vi.spyOn(apiClient, 'createRun').mockImplementation(async ({ scenario_id, policy }) => ({
    run_id: `run-${policy}`,
    scenario: {
      id: scenario_id,
      seed: 42,
      topology: { template: 'campus' },
      traffic: INITIAL_FLOWS,
      events: [{ step: 1, kind: 'fail', links: ['L_DC_PRI'] }],
      config: { order: 'class_size_desc', max_paths: 3, congestion_lambda: 0, util_cap: 1.0 },
    },
    topology: CAMPUS_TOPOLOGY,
    flows: INITIAL_FLOWS,
    snapshot: MOCK_STEP0_SNAPSHOT,
  }) as RunResponse);
  vi.spyOn(apiClient, 'applyEvent').mockImplementation(async (runId) =>
    runId === 'run-S2' ? MOCK_STEP1_S2_SNAPSHOT : MOCK_STEP1_S0_QOS_SNAPSHOT,
  );
  vi.spyOn(apiClient, 'resetRun').mockResolvedValue(MOCK_STEP0_SNAPSHOT);
}

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
    stubApi();
  });

  it('loads the first listed scenario into both panels with one run per policy (Task 1.5 & 3.1)', async () => {
    render(<App />);

    expect(await screen.findByTestId('quick-fail-btn')).toHaveTextContent('L_DC_PRI');
    expect(apiClient.createRun).toHaveBeenCalledWith({ scenario_id: 'campus-template', policy: 'S0-QoS' });
    expect(apiClient.createRun).toHaveBeenCalledWith({ scenario_id: 'campus-template', policy: 'S2' });
    expect(screen.getByText('42')).toBeInTheDocument(); // seed from the API's scenario
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
    const applyEventSpy = vi.mocked(apiClient.applyEvent);

    render(<App />);
    await screen.findByTestId('quick-fail-btn'); // runs created

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
      expect(applyEventSpy).toHaveBeenCalledTimes(2);
    });
    // The same event goes to each panel's own run
    const calledRuns = applyEventSpy.mock.calls.map(([runId]) => runId).sort();
    expect(calledRuns).toEqual(['run-S0-QoS', 'run-S2']);
    expect(applyEventSpy.mock.calls[0][1]).toMatchObject({ kind: 'fail', links: ['L_DC_PRI'] });

    // Verify step incremented in both panels
    await waitFor(() => {
      expect(screen.getAllByText('Step 1')).toHaveLength(2);
    });
  });

  it('displays error banner on request failure while retaining snapshots (Task 2.5)', async () => {
    vi.mocked(apiClient.applyEvent).mockRejectedValueOnce(new Error('Simulated backend timeout'));

    render(<App />);
    await screen.findByTestId('quick-fail-btn');

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
    const createRunSpy = vi.mocked(apiClient.createRun);
    const applyEventSpy = vi.mocked(apiClient.applyEvent);

    render(<App />);
    await screen.findByTestId('quick-fail-btn');

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
      expect(createRunSpy).toHaveBeenCalledWith({ scenario_id: 'campus-template', policy: 'S0' });
    });
    // ...and replays the failure onto the new S0 run
    await waitFor(() => {
      expect(applyEventSpy).toHaveBeenCalledWith('run-S0', expect.objectContaining({ links: ['L_DC_PRI'] }));
    });
  });

  it('resets both panels to step 0 after an event (Task 4.3)', async () => {
    render(<App />);
    fireEvent.click(await screen.findByTestId('quick-fail-btn'));
    await waitFor(() => expect(screen.getAllByText('Step 1')).toHaveLength(2));

    fireEvent.click(screen.getByText('Reset'));

    await waitFor(() => {
      expect(apiClient.resetRun).toHaveBeenCalledWith('run-S0-QoS');
      expect(apiClient.resetRun).toHaveBeenCalledWith('run-S2');
      expect(screen.getAllByText('Step 0')).toHaveLength(2);
    });
  });

  it('loads a selected scenario into both panels (Task 4.3)', async () => {
    vi.mocked(apiClient.getScenarios).mockResolvedValue([
      { id: 'campus-template', name: 'Campus', description: 'test campus' },
      { id: 'diamond', name: 'Diamond', description: 'four nodes' },
    ]);
    render(<App />);
    await screen.findByTestId('quick-fail-btn');

    fireEvent.change(screen.getByTestId('scenario-select'), { target: { value: 'diamond' } });

    await waitFor(() => {
      expect(apiClient.createRun).toHaveBeenCalledWith({ scenario_id: 'diamond', policy: 'S0-QoS' });
      expect(apiClient.createRun).toHaveBeenCalledWith({ scenario_id: 'diamond', policy: 'S2' });
    });
  });
});
