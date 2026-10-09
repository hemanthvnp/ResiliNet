import React, { useState, useEffect, useRef } from 'react';
import { TopologyGraph, ViewportState } from './components/TopologyGraph';
import { KpiStrip } from './components/KpiStrip';
import { FlowTable, CLASS_COLORS } from './components/FlowTable';
import { DecisionPanel } from './components/DecisionPanel';
import { apiClient } from './api/client';
import { BaselinePolicy, NetworkProvider, useNetwork } from './context/NetworkStore';
import { Event, ScenarioInfo, Snapshot } from './types/contract';

export type ViewLayoutMode = 'side-by-side' | 'stacked' | 'toggle';

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
  const [activeTogglePolicy, setActiveTogglePolicy] = useState<'baseline' | 's2'>('s2');

  // Interactive failure injection controls
  const [selectedLinkToToggle, setSelectedLinkToToggle] = useState<string>('');
  const targetLink = selectedLinkToToggle || topology.links[0]?.id || '';
  // The scenario's first scripted failure (the demo's primary uplink), if it has one
  const scriptedFailure = scenarioEvents.find((e) => e.kind === 'fail' && e.links.length > 0)?.links ?? [];
  const scriptedDown = scriptedFailure.length > 0 && scriptedFailure.every((l) => rightPanel.snapshot.link_state[l] === 'down');

  const [scenarios, setScenarios] = useState<ScenarioInfo[]>([]);

  // Two runs per scenario, one per panel (Task 3.1); the baseline panel keeps its chosen policy
  const loadScenario = async (scenario_id: string, baseline: BaselinePolicy) => {
    try {
      dispatch({ type: 'SET_IN_FLIGHT', payload: true });
      const [leftRes, rightRes] = await Promise.all([
        apiClient.createRun({ scenario_id, policy: baseline }),
        apiClient.createRun({ scenario_id, policy: 'S2' }),
      ]);

      dispatch({
        type: 'INIT_SCENARIO',
        payload: {
          scenarioId: scenario_id,
          seed: rightRes.scenario.seed,
          scenarioEvents: rightRes.scenario.events,
          topology: rightRes.topology,
          flows: rightRes.flows,
          left: { policy: baseline, runId: leftRes.run_id, snapshot: leftRes.snapshot },
          right: { policy: 'S2', runId: rightRes.run_id, snapshot: rightRes.snapshot },
        },
      });
    } catch (err: any) {
      dispatch({
        type: 'APPLY_EVENT_FAILURE',
        payload: { error: err.message || `Failed to load scenario ${scenario_id}` },
      });
    }
  };

  // Load the first listed scenario on mount
  useEffect(() => {
    apiClient
      .getScenarios()
      .then((list) => {
        if (list.length === 0) throw new Error('The API lists no scenarios');
        setScenarios(list);
        return loadScenario(list[0].id, 'S0-QoS');
      })
      .catch((err) => dispatch({ type: 'APPLY_EVENT_FAILURE', payload: { error: err.message } }));
  }, [dispatch]);

  // Click-to-fail / Click-to-recover handler with click lock (Task 2.3 & 3.1)
  const eventLock = useRef(false);
  const handleLinkClick = (linkId: string, currentStatus: 'up' | 'down') =>
    handleLinksEvent([linkId], currentStatus === 'up' ? 'fail' : 'recover');

  // One event to both panels; several links fail together as one simultaneous event
  const handleLinksEvent = async (links: string[], kind: 'fail' | 'recover') => {
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
        scenario_id: scenarioId,
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
    <div className="app-container" data-testid="app-root">
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
            disabled={inFlight}
            data-testid="scenario-select"
            aria-label="Scenario"
          >
            {scenarios.map((sc) => (
              <option key={sc.id} value={sc.id} title={sc.description}>
                {sc.name}
              </option>
            ))}
          </select>

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
            <span>{inFlight ? 'In Flight...' : `Step: ${currentStep}`}</span>
          </div>

          <button
            className="btn-secondary"
            onClick={handleReset}
            disabled={inFlight}
            title="Reset both panels to Step 0"
          >
            Reset
          </button>
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
        <div className="failure-toolbar" data-testid="failure-toolbar">
          <div className="failure-toolbar-title">
            <span className="failure-icon">⚡</span>
            <span>Failure Injection:</span>
          </div>

          {scriptedFailure.length > 0 && (
            <button
              className={`btn-failure-quick ${scriptedDown ? 'btn-recover' : 'btn-fail'}`}
              onClick={() => handleLinksEvent(scriptedFailure, scriptedDown ? 'recover' : 'fail')}
              disabled={inFlight}
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
              disabled={inFlight}
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
              disabled={inFlight || !targetLink}
              data-testid="toggle-link-btn"
            >
              {rightPanel.snapshot.link_state[targetLink] === 'down'
                ? '↺ Recover Link'
                : '⚡ Fail Link'}
            </button>
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
                    disabled={inFlight}
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
                label={`Step ${currentStep}`}
              />

              <div className="graph-viewport-wrapper">
                <div className="graph-instruction-banner">Click any link to fail / recover</div>
                <TopologyGraph
                  topology={topology}
                  snapshot={leftPanel.snapshot}
                  onLinkClick={handleLinkClick}
                  highlightedArcs={arcsFor(leftPanel.snapshot)}
                  highlightColor={highlightColor}
                  readOnly={inFlight}
                  viewport={sharedViewport}
                  onViewportChange={setSharedViewport}
                />
              </div>

              <DecisionPanel decision={decisionFor(leftPanel.snapshot)} />

              <div className="legend-strip">
                <div className="legend-item">
                  <div className="legend-color-box" style={{ background: '#10b981' }} />
                  <span>Util &lt; 50%</span>
                </div>
                <div className="legend-item">
                  <div className="legend-color-box" style={{ background: '#f59e0b' }} />
                  <span>Util 50-90%</span>
                </div>
                <div className="legend-item">
                  <div className="legend-color-box" style={{ background: '#d946ef' }} />
                  <span>Overload &gt; 100%</span>
                </div>
                <div className="legend-item">
                  <div className="legend-color-box" style={{ background: '#ef4444', border: '1px dashed #ffffff' }} />
                  <span>Failed Link</span>
                </div>
              </div>
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
                label={`Step ${currentStep}`}
              />

              <div className="graph-viewport-wrapper">
                <div className="graph-instruction-banner">Synchronized parallel view</div>
                <TopologyGraph
                  topology={topology}
                  snapshot={rightPanel.snapshot}
                  onLinkClick={handleLinkClick}
                  highlightedArcs={arcsFor(rightPanel.snapshot)}
                  highlightColor={highlightColor}
                  readOnly={inFlight}
                  viewport={sharedViewport}
                  onViewportChange={setSharedViewport}
                />
              </div>

              <DecisionPanel decision={decisionFor(rightPanel.snapshot)} />

              <div className="legend-strip">
                <div className="legend-item">
                  <div className="legend-color-box" style={{ background: highlightColor ?? '#38bdf8' }} />
                  <span>Selected Flow Route (class colour)</span>
                </div>
                <div className="legend-item">
                  <div className="legend-color-box" style={{ background: '#10b981' }} />
                  <span>Safe Margin</span>
                </div>
                <div className="legend-item">
                  <div className="legend-color-box" style={{ background: '#d946ef' }} />
                  <span>Overload (0 in S2)</span>
                </div>
              </div>
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
