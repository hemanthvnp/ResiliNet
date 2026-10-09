import React, { useState, useEffect, useRef } from 'react';
import { TopologyGraph, ViewportState } from './components/TopologyGraph';
import { KpiStrip } from './components/KpiStrip';
import { Legend } from './components/Legend';
import { FlowTable, CLASS_COLORS } from './components/FlowTable';
import { DecisionPanel } from './components/DecisionPanel';
import { BenchmarkChart, BenchmarkRow, parseBenchmarkCsv } from './components/BenchmarkChart';
import { apiClient } from './api/client';
import { BaselinePolicy, NetworkProvider, useNetwork } from './context/NetworkStore';
import { CompareResponse, Event, Scenario, ScenarioInfo, Snapshot } from './types/contract';

export type ViewLayoutMode = 'side-by-side' | 'stacked' | 'toggle';

// The seed a generated topology was actually built with (after any retry), else the scenario's
const effectiveSeed = (sc: Scenario) => ('generator' in sc.topology ? sc.topology.seed : sc.seed);

// FileReader rather than file.text(): same result in browsers, and it also runs under jsdom in tests
const readText = (file: File) =>
  new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file);
  });

export const ResiliNetDashboard: React.FC = () => {
  const { state, dispatch } = useNetwork();
  const {
    scenarioId,
    seed,
    scenarioEvents,
    topology,
    flows,
    leftPanel,
    rightPanel,
    selectedFlowId,
    inFlight,
    error,
    eventHistory,
  } = state;

  const currentStep = eventHistory.length;

  // Viewport synchronization across panels (Task 3.2)
  const [sharedViewport, setSharedViewport] = useState<ViewportState | undefined>(undefined);

  // Layout mode (Task 3.5 cut-line fallback)
  const [layoutMode, setLayoutMode] = useState<ViewLayoutMode>('side-by-side');

  // Demo mode for the projector: large KPIs, secondary labels hidden (task 5.4). Open the
  // app with ?demo=1 on the demo laptop to start in it.
  const [demoMode, setDemoMode] = useState(() => new URLSearchParams(window.location.search).get('demo') === '1');
  const [activeTogglePolicy, setActiveTogglePolicy] = useState<'baseline' | 's2'>('s2');

  // Interactive failure injection controls
  const [selectedLinkToToggle, setSelectedLinkToToggle] = useState<string>('');
  const targetLink = selectedLinkToToggle || topology.links[0]?.id || '';
  // The scenario's first scripted failure (the demo's primary uplink), if it has one
  const scriptedFailure = scenarioEvents.find((e) => e.kind === 'fail' && e.links.length > 0)?.links ?? [];
  const scriptedDown = scriptedFailure.length > 0 && scriptedFailure.every((l) => rightPanel.snapshot.link_state[l] === 'down');

  const [scenarios, setScenarios] = useState<ScenarioInfo[]>([]);
  const [bench, setBench] = useState<{ rows: BenchmarkRow[]; source: string } | null>(null);
  const loadBenchmark = async (file: File) => {
    try {
      setBench({ rows: parseBenchmarkCsv(await readText(file)), source: file.name });
    } catch (err: any) {
      dispatch({ type: 'APPLY_EVENT_FAILURE', payload: { error: `Cannot load ${file.name}: ${err.message}` } });
    }
  };
  const [isMock, setIsMock] = useState(false); // the API answered from fixtures (X-Mock header)

  // Generate-network form (task 4.4). Defaults are B's campus generator defaults (about 50 nodes).
  const [generated, setGenerated] = useState<Scenario | null>(null);
  const [gen, setGen] = useState({ buildings: 37, redundancy: 0.5, seed: 1 });
  const generateNetwork = () =>
    loadScenario(
      {
        id: `generated-b${gen.buildings}-r${gen.redundancy}-s${gen.seed}`,
        seed: gen.seed,
        topology: { generator: 'campus', buildings: gen.buildings, redundancy: gen.redundancy, seed: gen.seed },
        traffic: {
          generator: 'campus',
          n_flows: 200,
          load_factor: 0.5,
          class_mix: { 0: 0.1, 1: 0.4, 2: 0.5 },
          seed: gen.seed,
        },
        events: [],
        config: { order: 'class_size_desc', max_paths: 3, congestion_lambda: 0, util_cap: 1.0 },
      },
      leftPanel.policy as BaselinePolicy,
    );

  // A saved `compare --out` file, played back with no server (task 5.2): the demo's fallback
  const [saved, setSaved] = useState<{ name: string; left: Snapshot[]; right: Snapshot[] } | null>(null);
  const [savedIndex, setSavedIndex] = useState(0);
  const locked = inFlight || saved !== null; // live controls are off while a saved run plays
  const displayStep = saved ? rightPanel.snapshot.step : currentStep;

  const showSaved = (run: { left: Snapshot[]; right: Snapshot[] }, index: number) => {
    setSavedIndex(index);
    dispatch({ type: 'SHOW_SNAPSHOTS', payload: { left: run.left[index], right: run.right[index] } });
  };

  const loadSavedRun = async (file: File) => {
    try {
      const run: CompareResponse = JSON.parse(await readText(file));
      const right = run.snapshots?.['S2'];
      const baseline = (['S0-QoS', 'S0'] as const).find((p) => run.snapshots?.[p]?.length);
      if (!run.topology || !run.flows || !right?.length || !baseline) {
        throw new Error('Not a saved comparison: it needs topology, flows and snapshots for S2 and S0-QoS or S0');
      }
      const left = run.snapshots[baseline];
      if (left.length !== right.length) throw new Error('The saved baseline and S2 runs have different step counts');
      dispatch({
        type: 'INIT_SCENARIO',
        payload: {
          scenarioId: run.scenario.id,
          seed: run.scenario.seed,
          scenarioEvents: run.scenario.events,
          topology: run.topology,
          flows: run.flows,
          left: { policy: baseline, runId: '', snapshot: left[0] },
          right: { policy: 'S2', runId: '', snapshot: right[0] },
        },
      });
      setSaved({ name: file.name, left, right });
      setSavedIndex(0);
    } catch (err: any) {
      dispatch({ type: 'APPLY_EVENT_FAILURE', payload: { error: `Cannot load ${file.name}: ${err.message}` } });
    }
  };

  // Two runs per scenario, one per panel (Task 3.1); the baseline panel keeps its chosen policy
  // `source` is a built-in scenario id, or an inline scenario such as a generated campus
  const loadScenario = async (source: string | Scenario, baseline: BaselinePolicy) => {
    const choice = typeof source === 'string' ? { scenario_id: source } : { scenario: source };
    try {
      dispatch({ type: 'SET_IN_FLIGHT', payload: true });
      const [leftRes, rightRes] = await Promise.all([
        apiClient.createRun({ ...choice, policy: baseline }),
        apiClient.createRun({ ...choice, policy: 'S2' }),
      ]);
      // Replays of a generated network need the scenario itself, as the server ran it
      setGenerated(typeof source === 'string' ? null : rightRes.scenario);

      dispatch({
        type: 'INIT_SCENARIO',
        payload: {
          scenarioId: rightRes.scenario.id,
          seed: effectiveSeed(rightRes.scenario),
          scenarioEvents: rightRes.scenario.events,
          topology: rightRes.topology,
          flows: rightRes.flows,
          left: { policy: baseline, runId: leftRes.run_id, snapshot: leftRes.snapshot },
          right: { policy: 'S2', runId: rightRes.run_id, snapshot: rightRes.snapshot },
        },
      });
      setIsMock(apiClient.mock);
    } catch (err: any) {
      dispatch({
        type: 'APPLY_EVENT_FAILURE',
        payload: { error: err.message || `Failed to load scenario ${typeof source === 'string' ? source : source.id}` },
      });
    }
  };

  // Load the first listed scenario from the API (on mount, and when leaving a saved run)
  const loadLive = () =>
    apiClient
      .getScenarios()
      .then((list) => {
        if (list.length === 0) throw new Error('The API lists no scenarios');
        setScenarios(list);
        // ?scenario=<id> opens a given scenario, e.g. 02_uplink_failure for the demo; otherwise the first
        const wanted = new URLSearchParams(window.location.search).get('scenario');
        const chosen = list.find((sc) => sc.id === wanted) ?? list[0];
        return loadScenario(chosen.id, 'S0-QoS').then(() => {
          if (wanted && chosen.id !== wanted) {
            const ids = list.map((sc) => sc.id).join(', ');
            throw new Error(`Unknown scenario '${wanted}' in the URL; showing ${chosen.id}. Known: ${ids}`);
          }
        });
      })
      .catch((err) => dispatch({ type: 'APPLY_EVENT_FAILURE', payload: { error: err.message } }));

  useEffect(() => {
    loadLive();
  }, [dispatch]);

  // Click-to-fail / Click-to-recover handler with click lock (Task 2.3 & 3.1)
  const eventLock = useRef(false);
  const handleLinkClick = (linkId: string, currentStatus: 'up' | 'down') =>
    handleLinksEvent([linkId], currentStatus === 'up' ? 'fail' : 'recover');

  // One event to both panels; several links fail together as one simultaneous event
  const handleLinksEvent = async (links: string[], kind: 'fail' | 'recover') => {
    if (saved) return; // a saved run is played back, not edited
    // Click lock. `inFlight` only updates on the next render, so a fast double click could
    // pass it and send the event twice; the ref is set synchronously.
    if (inFlight || eventLock.current) {
      console.warn('Click ignored: request in flight');
      return;
    }
    eventLock.current = true;

    dispatch({ type: 'SET_IN_FLIGHT', payload: true });
    const event: Event = { step: currentStep + 1, kind, links };

    try {
      // Parallel dispatch to both baseline and S2 engines (Task 3.1)
      const [leftSnapshot, rightSnapshot] = await Promise.all([
        apiClient.applyEvent(leftPanel.runId, event),
        apiClient.applyEvent(rightPanel.runId, event),
      ]);

      dispatch({
        type: 'APPLY_EVENT_SUCCESS',
        payload: {
          event,
          leftSnapshot,
          rightSnapshot,
        },
      });
    } catch (err: any) {
      dispatch({
        type: 'APPLY_EVENT_FAILURE',
        payload: { error: err.message || `Failed to apply ${kind} event for ${links.join(', ')}` },
      });
    } finally {
      eventLock.current = false;
    }
  };

  // Baseline Policy Switch with History Replay (Task 3.3)
  const handleBaselinePolicyChange = async (newPolicy: 'S0-QoS' | 'S0') => {
    if (inFlight || newPolicy === leftPanel.policy) return;

    dispatch({ type: 'SET_IN_FLIGHT', payload: true });
    try {
      // Create new session for the selected baseline policy
      const { run_id, snapshot: initSnapshot } = await apiClient.createRun({
        ...(generated ? { scenario: generated } : { scenario_id: scenarioId }),
        policy: newPolicy,
      });

      let currentSnapshot = initSnapshot;

      // Replay all previous events in order onto the new baseline run
      for (const pastEvent of eventHistory) {
        currentSnapshot = await apiClient.applyEvent(run_id, pastEvent);
      }

      dispatch({
        type: 'REPLAY_BASELINE_SUCCESS',
        payload: {
          policy: newPolicy,
          runId: run_id,
          snapshot: currentSnapshot,
        },
      });
    } catch (err: any) {
      dispatch({
        type: 'APPLY_EVENT_FAILURE',
        payload: { error: err.message || 'Failed to replay event history on baseline switch' },
      });
    }
  };

  const handleReset = async () => {
    if (inFlight) return;
    dispatch({ type: 'SET_IN_FLIGHT', payload: true });
    try {
      const [left, right] = await Promise.all([
        apiClient.resetRun(leftPanel.runId),
        apiClient.resetRun(rightPanel.runId),
      ]);
      dispatch({ type: 'RESET', payload: { left, right } });
    } catch (err: any) {
      dispatch({
        type: 'APPLY_EVENT_FAILURE',
        payload: { error: err.message || 'Failed to reset sessions' },
      });
    }
  };

  // Each panel explains its own decision for the selected flow, when that flow was rerouted
  const decisionFor = (snapshot: Snapshot) => snapshot.decisions.find((d) => d.flow_id === selectedFlowId);

  // Each panel highlights its own routes for the selected flow, in the flow's class colour
  const arcsFor = (snapshot: Snapshot) =>
    (selectedFlowId ? snapshot.allocation.results[selectedFlowId]?.paths ?? [] : []).flatMap((p) => p.arcs);
  const selectedCls = flows.find((f) => f.id === selectedFlowId)?.cls;
  const highlightColor = selectedCls === undefined ? undefined : CLASS_COLORS[selectedCls];

  return (
    <div className={`app-container ${demoMode ? 'demo-mode' : ''}`} data-testid="app-root">
      {/* Top Header Controls */}
      <header className="app-header">
        <div className="brand-section">
          <div className="brand-title">ResiliNet</div>
          <div className="brand-subtitle">Campus Network Rerouter · Problem Statement 4</div>
        </div>

        <div className="header-controls">
          {/* Layout switcher (Task 3.5) */}
          <div className="layout-switcher-group" data-testid="layout-switcher">
            <button
              className={`layout-btn ${layoutMode === 'side-by-side' ? 'layout-btn-active' : ''}`}
              onClick={() => setLayoutMode('side-by-side')}
              title="Side-by-side view"
            >
              Side-by-Side
            </button>
            <button
              className={`layout-btn ${layoutMode === 'stacked' ? 'layout-btn-active' : ''}`}
              onClick={() => setLayoutMode('stacked')}
              title="Stacked panels"
            >
              Stacked
            </button>
            <button
              className={`layout-btn ${layoutMode === 'toggle' ? 'layout-btn-active' : ''}`}
              onClick={() => setLayoutMode('toggle')}
              title="Toggle between policies"
            >
              Toggle
            </button>
          </div>

          <select
            className="panel-selector"
            value={scenarioId}
            onChange={(e) => loadScenario(e.target.value, leftPanel.policy as BaselinePolicy)}
            disabled={locked}
            data-testid="scenario-select"
            aria-label="Scenario"
          >
            {scenarios.map((sc) => (
              <option key={sc.id} value={sc.id} title={sc.description}>
                {sc.name}
              </option>
            ))}
            {generated && <option value={generated.id}>Generated network</option>}
          </select>

          {isMock && !saved && (
            <div
              className="badge-seed badge-mock"
              data-testid="mock-badge"
              title="The API is in mock mode: snapshots come from fixtures, events do not reroute"
            >
              MOCK DATA
            </div>
          )}

          <div className="badge-seed">
            <span>Seed:</span>
            <strong>{seed}</strong>
          </div>

          <div
            className="badge-seed"
            style={{
              background: inFlight ? 'rgba(239, 68, 68, 0.15)' : 'rgba(16, 185, 129, 0.15)',
              color: inFlight ? '#f87171' : '#34d399',
            }}
          >
            <span>{inFlight ? 'In Flight...' : `Step: ${displayStep}`}</span>
          </div>

          <button
            className="btn-secondary"
            onClick={handleReset}
            disabled={locked}
            title="Reset both panels to Step 0"
          >
            Reset
          </button>

          <button
            className={`btn-secondary ${demoMode ? 'btn-primary' : ''}`}
            onClick={() => setDemoMode((on) => !on)}
            aria-pressed={demoMode}
            data-testid="demo-mode-btn"
          >
            Demo mode
          </button>

          <label className="btn-secondary" data-testid="saved-run-label">
            Load saved run
            <input
              type="file"
              accept="application/json,.json"
              hidden
              disabled={inFlight}
              data-testid="saved-run-input"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) loadSavedRun(file);
                e.target.value = ''; // the same file can be loaded again
              }}
            />
          </label>

          {saved && (
            <div className="badge-seed" data-testid="saved-run-bar">
              <span>Saved run {saved.name}</span>
              <button
                className="btn-secondary"
                onClick={() => showSaved(saved, savedIndex - 1)}
                disabled={savedIndex === 0}
                aria-label="Previous step"
              >
                ◀
              </button>
              <strong>
                {savedIndex + 1} / {saved.right.length}
              </strong>
              <button
                className="btn-secondary"
                onClick={() => showSaved(saved, savedIndex + 1)}
                disabled={savedIndex === saved.right.length - 1}
                aria-label="Next step"
              >
                ▶
              </button>
              <button
                className="btn-secondary"
                onClick={() => {
                  setSaved(null);
                  loadLive();
                }}
              >
                Back to live
              </button>
            </div>
          )}
        </div>
      </header>

      {/* Main Dashboard */}
      <main className="dashboard-main">
        {/* Error Notification Banner (Task 2.5 & Task 3.1) */}
        {error && (
          <div className="error-banner" data-testid="error-banner">
            <div className="error-message-text">
              <strong>Error:</strong> {error}
            </div>
            <button
              className="btn-secondary error-dismiss-btn"
              onClick={() => dispatch({ type: 'CLEAR_ERROR' })}
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Interactive Failure Injection Toolbar */}
        {/* The two control bars stack normally and share one row in demo mode (task 5.4) */}
        <div className="controls-row">
        <form
          className="failure-toolbar generate-form"
          data-testid="generate-form"
          onSubmit={(e) => {
            e.preventDefault();
            generateNetwork();
          }}
        >
          <div className="failure-toolbar-title">
            <span>Generate network:</span>
          </div>
          <label>
            Buildings{' '}
            <input
              type="number"
              min={1}
              max={60}
              value={gen.buildings}
              onChange={(e) => setGen({ ...gen, buildings: Number(e.target.value) })}
              data-testid="gen-buildings"
            />
          </label>
          <label>
            Redundancy{' '}
            <input
              type="number"
              min={0}
              max={1}
              step={0.1}
              value={gen.redundancy}
              onChange={(e) => setGen({ ...gen, redundancy: Number(e.target.value) })}
              data-testid="gen-redundancy"
            />
          </label>
          <label>
            Seed{' '}
            <input
              type="number"
              min={0}
              step={1}
              value={gen.seed}
              onChange={(e) => setGen({ ...gen, seed: Number(e.target.value) })}
              data-testid="gen-seed"
            />
          </label>
          <button type="submit" className="btn-secondary" disabled={locked} data-testid="generate-btn">
            Generate
          </button>
        </form>

        <div className="failure-toolbar" data-testid="failure-toolbar">
          <div className="failure-toolbar-title">
            <span className="failure-icon">⚡</span>
            <span>Failure Injection:</span>
          </div>

          {scriptedFailure.length > 0 && (
            <button
              className={`btn-failure-quick ${scriptedDown ? 'btn-recover' : 'btn-fail'}`}
              onClick={() => handleLinksEvent(scriptedFailure, scriptedDown ? 'recover' : 'fail')}
              disabled={locked}
              data-testid="quick-fail-btn"
            >
              {scriptedDown
                ? `↺ Recover scenario failure (${scriptedFailure.join(', ')})`
                : `⚡ Fail scenario link${scriptedFailure.length > 1 ? 's' : ''} (${scriptedFailure.join(', ')})`}
            </button>
          )}

          <div className="failure-select-group">
            <label htmlFor="link-select">Or target link:</label>
            <select
              id="link-select"
              className="panel-selector"
              value={targetLink}
              onChange={(e) => setSelectedLinkToToggle(e.target.value)}
              disabled={locked}
              data-testid="link-select"
            >
              {topology.links.map((link) => {
                const status = rightPanel.snapshot.link_state[link.id] || 'up';
                return (
                  <option key={link.id} value={link.id}>
                    {link.id} ({link.u} ↔ {link.v}) [{status.toUpperCase()}]
                  </option>
                );
              })}
            </select>
            <button
              className="btn-secondary"
              onClick={() => {
                const curStatus = rightPanel.snapshot.link_state[targetLink] === 'down' ? 'down' : 'up';
                handleLinkClick(targetLink, curStatus);
              }}
              disabled={locked || !targetLink}
              data-testid="toggle-link-btn"
            >
              {rightPanel.snapshot.link_state[targetLink] === 'down'
                ? '↺ Recover Link'
                : '⚡ Fail Link'}
            </button>
          </div>
        </div>
        </div>

        {/* Toggle Mode Selector Bar (when in toggle layout mode) */}
        {layoutMode === 'toggle' && (
          <div className="toggle-policy-bar" data-testid="toggle-policy-bar">
            <button
              className={`btn-secondary ${activeTogglePolicy === 'baseline' ? 'btn-primary' : ''}`}
              onClick={() => setActiveTogglePolicy('baseline')}
            >
              Baseline ({leftPanel.policy})
            </button>
            <button
              className={`btn-secondary ${activeTogglePolicy === 's2' ? 'btn-primary' : ''}`}
              onClick={() => setActiveTogglePolicy('s2')}
            >
              S2 Resilient (Ours)
            </button>
          </div>
        )}

        {/* Comparison Grid (Side-by-side vs Stacked vs Toggle) */}
        <div
          className={`comparison-grid ${
            layoutMode === 'stacked'
              ? 'comparison-grid-stacked'
              : layoutMode === 'toggle'
              ? 'comparison-grid-single'
              : ''
          }`}
        >
          {/* Left Panel: Baseline */}
          {(layoutMode !== 'toggle' || activeTogglePolicy === 'baseline') && (
            <div className="panel-card" data-testid="baseline-panel">
              <div className="panel-header">
                <div className="panel-title-area">
                  <span className="panel-title">Baseline Network</span>
                  <select
                    className="panel-selector"
                    value={leftPanel.policy}
                    onChange={(e) =>
                      handleBaselinePolicyChange(e.target.value as 'S0-QoS' | 'S0')
                    }
                    disabled={locked}
                    data-testid="baseline-selector"
                  >
                    <option value="S0-QoS">S0-QoS (Priority Queues)</option>
                    <option value="S0">S0 (Naive Dijkstra)</option>
                  </select>
                </div>
              </div>

              <KpiStrip
                metrics={leftPanel.snapshot.metrics}
                policyName={leftPanel.policy}
                label={`Step ${displayStep}`}
              />

              <div className="graph-viewport-wrapper">
                <div className="graph-instruction-banner">Click any link to fail / recover</div>
                <TopologyGraph
                  topology={topology}
                  snapshot={leftPanel.snapshot}
                  onLinkClick={handleLinkClick}
                  highlightedArcs={arcsFor(leftPanel.snapshot)}
                  highlightColor={highlightColor}
                  readOnly={locked}
                  viewport={sharedViewport}
                  onViewportChange={setSharedViewport}
                />
              </div>

              <DecisionPanel decision={decisionFor(leftPanel.snapshot)} />

              <Legend />
            </div>
          )}

          {/* Right Panel: S2 Improved */}
          {(layoutMode !== 'toggle' || activeTogglePolicy === 's2') && (
            <div className="panel-card" data-testid="s2-panel">
              <div className="panel-header">
                <div className="panel-title-area">
                  <span className="panel-title">S2 Priority Residual Routing (Ours)</span>
                  <span className="policy-badge" style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#34d399' }}>
                    Splitting m=3
                  </span>
                </div>
              </div>

              <KpiStrip
                metrics={rightPanel.snapshot.metrics}
                policyName="S2-Resilient"
                label={`Step ${displayStep}`}
              />

              <div className="graph-viewport-wrapper">
                <div className="graph-instruction-banner">Synchronized parallel view</div>
                <TopologyGraph
                  topology={topology}
                  snapshot={rightPanel.snapshot}
                  onLinkClick={handleLinkClick}
                  highlightedArcs={arcsFor(rightPanel.snapshot)}
                  highlightColor={highlightColor}
                  readOnly={locked}
                  viewport={sharedViewport}
                  onViewportChange={setSharedViewport}
                />
              </div>

              <DecisionPanel decision={decisionFor(rightPanel.snapshot)} />

              <Legend />
            </div>
          )}
        </div>

        {/* Flow Inspection Table */}
        <FlowTable
          flows={flows}
          snapshot={rightPanel.snapshot}
          selectedFlowId={selectedFlowId}
          onSelectFlow={(id) => dispatch({ type: 'SELECT_FLOW', payload: id })}
        />

        {/* Benchmark chart from the benchmark's CSV, loaded from a file (task 5.1) */}
        <label className="btn-secondary" data-testid="benchmark-label">
          Load benchmark CSV
          <input
            type="file"
            accept=".csv,text/csv"
            hidden
            data-testid="benchmark-input"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) loadBenchmark(file);
              e.target.value = '';
            }}
          />
        </label>
        {bench && <BenchmarkChart key={bench.source} rows={bench.rows} source={bench.source} />}
      </main>
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <NetworkProvider>
      <ResiliNetDashboard />
    </NetworkProvider>
  );
};

export default App;
