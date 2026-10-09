import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import cytoscape from 'cytoscape';
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
  vi.spyOn(apiClient, 'createRun').mockImplementation(async (params) => ({
    run_id: `run-${params.policy}`,
    // an inline (generated) scenario comes back as run, with the seed the generator used after a retry
    scenario: 'scenario' in params ? { ...params.scenario, topology: { ...params.scenario.topology, seed: 10 } } : {
      id: params.scenario_id,
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
        edges: vi.fn(() => ({ nonempty: () => false, style: vi.fn() })),
      };
    }),
  };
});

describe('App Component (Phase 1 & Phase 2)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    apiClient.mock = false;
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

  it('sends recover for a link that is down (Task 2.3)', async () => {
    render(<App />);
    fireEvent.click(await screen.findByTestId('quick-fail-btn'));
    await waitFor(() => expect(screen.getByTestId('quick-fail-btn')).toHaveTextContent(/Recover/));

    fireEvent.click(screen.getByTestId('quick-fail-btn'));

    await waitFor(() =>
      expect(apiClient.applyEvent).toHaveBeenCalledWith('run-S2', expect.objectContaining({ kind: 'recover', links: ['L_DC_PRI'] })),
    );
  });

  it('ignores clicks while a request is in flight (Task 2.3)', async () => {
    vi.mocked(apiClient.applyEvent).mockImplementation(() => new Promise(() => {})); // never settles
    render(<App />);
    fireEvent.click(await screen.findByTestId('quick-fail-btn'));
    await waitFor(() => expect(apiClient.applyEvent).toHaveBeenCalledTimes(2)); // one per panel

    fireEvent.click(screen.getByTestId('quick-fail-btn'));
    (global as any).__mockCytoscapeTapEdge({ target: { id: () => 'L_CORE_INTER' } });

    expect(apiClient.applyEvent).toHaveBeenCalledTimes(2);
  });

  it('gives both panels the same node positions (Task 3.2)', async () => {
    vi.mocked(cytoscape).mockClear();
    render(<App />);
    await screen.findByTestId('quick-fail-btn');

    const positionsOf = (call: any[]) =>
      Object.fromEntries(
        call[0].elements.filter((e: any) => e.group === 'nodes').map((e: any) => [e.data.id, e.position]),
      );
    const drawn = vi.mocked(cytoscape).mock.calls.map(positionsOf).filter((p) => Object.keys(p).length > 0);
    expect(drawn.length).toBeGreaterThanOrEqual(2);
    for (const positions of drawn) expect(positions).toEqual(drawn[0]);
  });

  it('lands the replayed baseline on the same step after two events (Task 3.3)', async () => {
    const steps: Record<string, number> = {};
    vi.mocked(apiClient.applyEvent).mockImplementation(async (runId) => {
      steps[runId] = (steps[runId] ?? 0) + 1;
      const base = runId === 'run-S2' ? MOCK_STEP1_S2_SNAPSHOT : MOCK_STEP1_S0_QOS_SNAPSHOT;
      return { ...base, step: steps[runId] };
    });
    render(<App />);
    fireEvent.click(await screen.findByTestId('quick-fail-btn')); // fail
    await waitFor(() => expect(screen.getByTestId('quick-fail-btn')).toHaveTextContent(/Recover/));
    fireEvent.click(screen.getByTestId('quick-fail-btn')); // second event
    await waitFor(() => expect(screen.getAllByText('Step 2')).toHaveLength(2));

    fireEvent.change(screen.getByTestId('baseline-selector'), { target: { value: 'S0' } });

    await waitFor(() => expect(steps['run-S0']).toBe(2));
    await waitFor(() => expect((screen.getByTestId('baseline-selector') as HTMLSelectElement).value).toBe('S0'));
    expect(screen.queryByTestId('error-banner')).not.toBeInTheDocument();
  });

  it('toggles demo mode from the header (Task 5.4)', async () => {
    render(<App />);
    const root = await screen.findByTestId('app-root');
    expect(root).not.toHaveClass('demo-mode');

    fireEvent.click(screen.getByTestId('demo-mode-btn'));
    expect(root).toHaveClass('demo-mode');
    fireEvent.click(screen.getByTestId('demo-mode-btn'));
    expect(root).not.toHaveClass('demo-mode');
  });

  it('starts in demo mode when opened with ?demo=1 (Task 5.4)', async () => {
    window.history.pushState({}, '', '/?demo=1');
    try {
      render(<App />);
      expect(await screen.findByTestId('app-root')).toHaveClass('demo-mode');
    } finally {
      window.history.pushState({}, '', '/');
    }
  });

  it('plays back a saved comparison with no server (Task 5.2)', async () => {
    render(<App />);
    await screen.findByTestId('quick-fail-btn');
    vi.mocked(apiClient.applyEvent).mockClear();

    const saved = {
      scenario: { id: 'campus-template', seed: 7, topology: { template: 'campus' }, traffic: INITIAL_FLOWS, events: [], config: {} },
      topology: CAMPUS_TOPOLOGY,
      flows: INITIAL_FLOWS,
      table: [],
      snapshots: {
        'S0-QoS': [MOCK_STEP0_SNAPSHOT, MOCK_STEP1_S0_QOS_SNAPSHOT],
        S2: [MOCK_STEP0_SNAPSHOT, MOCK_STEP1_S2_SNAPSHOT],
      },
    };
    const file = new File([JSON.stringify(saved)], 'fallback-run.json', { type: 'application/json' });
    fireEvent.change(screen.getByTestId('saved-run-input'), { target: { files: [file] } });

    expect(await screen.findByTestId('saved-run-bar')).toHaveTextContent('1 / 2');
    expect(screen.getByText('7')).toBeInTheDocument(); // the saved scenario's seed
    expect(screen.getAllByText('Step 0')).toHaveLength(2);

    fireEvent.click(screen.getByLabelText('Next step'));

    // Each panel now shows its own saved step-1 snapshot
    await waitFor(() => expect(screen.getAllByText('Step 1')).toHaveLength(2));
    const overloads = screen.getAllByTestId('kpi-strip').map((k) => k.textContent);
    expect(overloads[0]).toContain(String(MOCK_STEP1_S0_QOS_SNAPSHOT.metrics.overloaded_arcs));
    expect(overloads[0]).not.toEqual(overloads[1]);
    // Live controls are off and nothing went to the API
    expect(screen.getByTestId('baseline-selector')).toBeDisabled();
    expect(apiClient.applyEvent).not.toHaveBeenCalled();
  });

  it('rejects a file that is not a saved comparison (Task 5.2)', async () => {
    render(<App />);
    await screen.findByTestId('quick-fail-btn');

    const file = new File(['{"snapshots": {}}'], 'wrong.json', { type: 'application/json' });
    fireEvent.change(screen.getByTestId('saved-run-input'), { target: { files: [file] } });

    expect(await screen.findByTestId('error-banner')).toHaveTextContent('Cannot load wrong.json: Not a saved comparison');
    expect(screen.queryByTestId('saved-run-bar')).not.toBeInTheDocument();
  });

  it('shows a MOCK badge only when the API answered from fixtures (review finding 27)', async () => {
    const { unmount } = render(<App />);
    await screen.findByTestId('quick-fail-btn');
    expect(screen.queryByTestId('mock-badge')).not.toBeInTheDocument();
    unmount();

    apiClient.mock = true;
    render(<App />);
    expect(await screen.findByTestId('mock-badge')).toHaveTextContent('MOCK DATA');
  });

  it('opens the scenario named by ?scenario=, for the demo laptop', async () => {
    vi.mocked(apiClient.getScenarios).mockResolvedValue([
      { id: '01_normal', name: 'Normal', description: '' },
      { id: '02_uplink_failure', name: 'Uplink failure', description: '' },
    ]);
    window.history.pushState({}, '', '/?scenario=02_uplink_failure');
    try {
      render(<App />);
      await screen.findByTestId('quick-fail-btn');
      expect(apiClient.createRun).toHaveBeenCalledWith({ scenario_id: '02_uplink_failure', policy: 'S2' });
      expect(apiClient.createRun).not.toHaveBeenCalledWith(expect.objectContaining({ scenario_id: '01_normal' }));
    } finally {
      window.history.pushState({}, '', '/');
    }
  });

  it('says so when ?scenario= names an unknown scenario, and shows the first one', async () => {
    window.history.pushState({}, '', '/?scenario=nope');
    try {
      render(<App />);
      expect(await screen.findByTestId('error-banner')).toHaveTextContent("Unknown scenario 'nope'");
      expect(apiClient.createRun).toHaveBeenCalledWith({ scenario_id: 'campus-template', policy: 'S2' });
    } finally {
      window.history.pushState({}, '', '/');
    }
  });

  it('generates a network, shows its effective seed and keeps it for baseline replay (Task 4.4)', async () => {
    render(<App />);
    await screen.findByTestId('quick-fail-btn');

    fireEvent.change(screen.getByTestId('gen-buildings'), { target: { value: '20' } });
    fireEvent.change(screen.getByTestId('gen-seed'), { target: { value: '9' } });
    fireEvent.click(screen.getByTestId('generate-btn'));

    const generatedRun = (policy: string) =>
      expect(apiClient.createRun).toHaveBeenCalledWith({
        scenario: expect.objectContaining({
          topology: { generator: 'campus', buildings: 20, redundancy: 0.5, seed: 9 },
          traffic: expect.objectContaining({ generator: 'campus', seed: 9 }),
        }),
        policy,
      });
    await waitFor(() => generatedRun('S2'));
    generatedRun('S0-QoS');
    // the generator retried and used seed 10: that is the seed shown
    expect(await screen.findByText('10')).toBeInTheDocument();

    fireEvent.change(screen.getByTestId('baseline-selector'), { target: { value: 'S0' } });
    await waitFor(() =>
      expect(apiClient.createRun).toHaveBeenCalledWith({
        scenario: expect.objectContaining({ topology: expect.objectContaining({ seed: 10 }) }),
        policy: 'S0',
      }),
    );
  });

  it('shows the benchmark chart from a loaded CSV (Task 5.1)', async () => {
    render(<App />);
    await screen.findByTestId('quick-fail-btn');
    const csv = 'seed,case,load_factor,policy,variant,dr\n0,uplink,1.0,S0-QoS,default,0.7\n0,uplink,1.0,S2,default,1.0\n';

    fireEvent.change(screen.getByTestId('benchmark-input'), {
      target: { files: [new File([csv], 'bench.csv', { type: 'text/csv' })] },
    });

    expect(await screen.findByTestId('benchmark-chart')).toHaveTextContent('Source: bench.csv');
  });

  it('replays the last event in three stages, and another event closes the player (Task 5.6)', async () => {
    render(<App />);
    fireEvent.click(await screen.findByTestId('quick-fail-btn'));
    await waitFor(() => expect(screen.getAllByText('Step 1')).toHaveLength(2));
    expect(screen.getByTestId('stage-player')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('stage-2'));
    expect(screen.getAllByText('Link fails: routes not yet recomputed')).toHaveLength(2);
    expect(screen.getByTestId('stage-caption')).toHaveTextContent('L_DC_PRI');
    expect(screen.getByTestId('stage-caption')).toHaveTextContent('3 flows were using it');

    fireEvent.click(screen.getByTestId('stage-1'));
    expect(screen.getAllByText('Before the event')).toHaveLength(2);

    fireEvent.click(screen.getByTestId('stage-3'));
    expect(screen.getAllByText('Rerouted')).toHaveLength(2);

    // another event: the panels show the current step again
    fireEvent.click(screen.getByTestId('quick-fail-btn'));
    await waitFor(() => expect(screen.queryByTestId('stage-caption')).not.toBeInTheDocument());
  });
});
