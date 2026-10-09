import React, { useEffect } from 'react';
import { TopologyGraph } from './components/TopologyGraph';
import { KpiStrip } from './components/KpiStrip';
import { FlowTable } from './components/FlowTable';
import { apiClient } from './api/client';
import { NetworkProvider, useNetwork } from './context/NetworkStore';
import { Event } from './types/contract';
import { MOCK_STEP0_SNAPSHOT } from './fixtures/mockData';

export const ResiliNetDashboard: React.FC = () => {
  const { state, dispatch } = useNetwork();
  const {
    seed,
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

  // Initialize initial sessions on mount
  useEffect(() => {
    async function loadInitial() {
      try {
        dispatch({ type: 'SET_IN_FLIGHT', payload: true });
        const { snapshot } = await apiClient.createRun({ policy: 'S2', seed });
        dispatch({
          type: 'INIT_SCENARIO',
          payload: {
            seed,
            topology,
            flows,
            initialSnapshot: snapshot,
          },
        });
      } catch (err: any) {
        dispatch({
          type: 'APPLY_EVENT_FAILURE',
          payload: { error: err.message || 'Failed to initialize session' },
        });
      }
    }
    loadInitial();
  }, [seed, dispatch, topology, flows]);

  // Click-to-fail / Click-to-recover handler with click lock (Task 2.3)
  const handleLinkClick = async (linkId: string, currentStatus: 'up' | 'down') => {
    if (inFlight) {
      console.warn('Click ignored: request in flight');
      return; // Click lock
    }

    dispatch({ type: 'SET_IN_FLIGHT', payload: true });
    const kind = currentStatus === 'up' ? 'fail' : 'recover';
    const event: Event = { step: currentStep + 1, kind, links: [linkId] };

    try {
      // Parallel dispatch to both baseline and S2 engines
      const [leftSnapshot, rightSnapshot] = await Promise.all([
        apiClient.applyEvent(leftPanel.runId, event, leftPanel.policy),
        apiClient.applyEvent(rightPanel.runId, event, rightPanel.policy),
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
        payload: { error: err.message || `Failed to apply ${kind} event for link ${linkId}` },
      });
    }
  };

  const handleReset = async () => {
    if (inFlight) return;
    dispatch({ type: 'SET_IN_FLIGHT', payload: true });
    try {
      await Promise.all([
        apiClient.resetRun(leftPanel.runId),
        apiClient.resetRun(rightPanel.runId),
      ]);
      dispatch({
        type: 'RESET',
        payload: { step0Snapshot: MOCK_STEP0_SNAPSHOT },
      });
    } catch (err: any) {
      dispatch({
        type: 'APPLY_EVENT_FAILURE',
        payload: { error: err.message || 'Failed to reset sessions' },
      });
    }
  };

  // Find active decision for the selected flow in S2
  const selectedDecision = rightPanel.snapshot.decisions?.find((d) => d.flow_id === selectedFlowId);

  // Selected flow's active paths for highlight
  const selectedPaths = rightPanel.snapshot.allocation?.results?.[selectedFlowId || '']?.paths || [];
  const highlightedArcs = selectedPaths.flatMap((p) => p.arcs);

  return (
    <div className="app-container" data-testid="app-root">
      {/* Top Header Controls */}
      <header className="app-header">
        <div className="brand-section">
          <div className="brand-title">ResiliNet</div>
          <div className="brand-subtitle">Campus Network Rerouter · Problem Statement 4</div>
        </div>

        <div className="header-controls">
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
        {/* Error Notification Banner (Task 2.5) */}
        {error && (
          <div className="error-banner" data-testid="error-banner">
            <div className="error-message-text">
              <strong>Request Error:</strong> {error}
            </div>
            <button
              className="btn-secondary error-dismiss-btn"
              onClick={() => dispatch({ type: 'CLEAR_ERROR' })}
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Active Flow Decision Banner */}
        {selectedDecision && (
          <div className="decision-banner" data-testid="decision-banner">
            <strong style={{ color: '#38bdf8' }}>Flow Explanation:</strong>
            <span>{selectedDecision.explanation}</span>
          </div>
        )}

        {/* Side-by-Side Comparison Grid */}
        <div className="comparison-grid">
          {/* Left Panel: Baseline */}
          <div className="panel-card" data-testid="baseline-panel">
            <div className="panel-header">
              <div className="panel-title-area">
                <span className="panel-title">Baseline Network</span>
                <select
                  className="panel-selector"
                  value={leftPanel.policy}
                  onChange={(e) =>
                    dispatch({
                      type: 'SET_BASELINE_POLICY',
                      payload: e.target.value as 'S0-QoS' | 'S0',
                    })
                  }
                  disabled={inFlight}
                >
                  <option value="S0-QoS">S0-QoS (Priority Queues)</option>
                  <option value="S0">S0 (Naive Dijkstra)</option>
                </select>
              </div>
            </div>

            <KpiStrip
              metrics={leftPanel.snapshot.metrics}
              policyName={leftPanel.policy}
              label={currentStep > 0 ? 'Post-Failure (Overloaded)' : 'Steady State'}
            />

            <div className="graph-viewport-wrapper">
              <div className="graph-instruction-banner">Click any link to fail / recover</div>
              <TopologyGraph
                topology={topology}
                snapshot={leftPanel.snapshot}
                onLinkClick={handleLinkClick}
                highlightedArcs={highlightedArcs}
                highlightColor="#f59e0b"
                readOnly={inFlight}
              />
            </div>

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

          {/* Right Panel: S2 Improved */}
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
              label={currentStep > 0 ? 'Capacity Protected' : 'Optimal Initial'}
            />

            <div className="graph-viewport-wrapper">
              <div className="graph-instruction-banner">Synchronized parallel view</div>
              <TopologyGraph
                topology={topology}
                snapshot={rightPanel.snapshot}
                onLinkClick={handleLinkClick}
                highlightedArcs={highlightedArcs}
                highlightColor="#38bdf8"
                readOnly={inFlight}
              />
            </div>

            <div className="legend-strip">
              <div className="legend-item">
                <div className="legend-color-box" style={{ background: '#38bdf8' }} />
                <span>Active Route Path</span>
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
