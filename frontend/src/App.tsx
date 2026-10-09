import React, { useState, useEffect } from 'react';
import { CAMPUS_TOPOLOGY, INITIAL_FLOWS, MOCK_STEP0_SNAPSHOT, MOCK_STEP1_S2_SNAPSHOT, MOCK_STEP1_S0_QOS_SNAPSHOT } from './fixtures/mockData';
import { Snapshot, Flow } from './types/contract';
import { TopologyGraph } from './components/TopologyGraph';
import { KpiStrip } from './components/KpiStrip';
import { FlowTable } from './components/FlowTable';
import { apiClient } from './api/client';

export const App: React.FC = () => {
  const [seed] = useState<number>(42);
  const [topology] = useState(CAMPUS_TOPOLOGY);
  const [flows] = useState<Flow[]>(INITIAL_FLOWS);

  // Left panel policy: S0-QoS (default) or S0
  const [baselinePolicy, setBaselinePolicy] = useState<'S0-QoS' | 'S0'>('S0-QoS');

  // Snapshots for baseline and S2
  const [baselineSnapshot, setBaselineSnapshot] = useState<Snapshot>(MOCK_STEP0_SNAPSHOT);
  const [s2Snapshot, setS2Snapshot] = useState<Snapshot>(MOCK_STEP0_SNAPSHOT);

  const [selectedFlowId, setSelectedFlowId] = useState<string | null>('F03');
  const [inFlight, setInFlight] = useState<boolean>(false);
  const [activeStep, setActiveStep] = useState<number>(0);

  // Initialize data on mount (Task 1.5)
  useEffect(() => {
    async function loadInitial() {
      try {
        const { snapshot } = await apiClient.createRun({ policy: 'S2', seed });
        setS2Snapshot(snapshot);
        setBaselineSnapshot(snapshot);
      } catch (err) {
        console.error('Failed to initialize run session:', err);
      }
    }
    loadInitial();
  }, [seed]);

  // Click-to-fail / Click-to-recover on links
  const handleLinkClick = async (linkId: string, currentStatus: 'up' | 'down') => {
    if (inFlight) return; // Click lock while in flight

    setInFlight(true);
    const newKind = currentStatus === 'up' ? 'fail' : 'recover';

    try {
      if (newKind === 'fail' && linkId === 'L_DC_PRI') {
        // Demonstrate the core comparison: L_DC_PRI down
        setBaselineSnapshot(MOCK_STEP1_S0_QOS_SNAPSHOT);
        setS2Snapshot(MOCK_STEP1_S2_SNAPSHOT);
        setActiveStep(1);
      } else {
        // Generic toggle / reset back to step 0
        setBaselineSnapshot(MOCK_STEP0_SNAPSHOT);
        setS2Snapshot(MOCK_STEP0_SNAPSHOT);
        setActiveStep(0);
      }
    } finally {
      setInFlight(false);
    }
  };

  const handleReset = () => {
    setBaselineSnapshot(MOCK_STEP0_SNAPSHOT);
    setS2Snapshot(MOCK_STEP0_SNAPSHOT);
    setActiveStep(0);
  };

  // Find active decision for the selected flow in S2
  const selectedDecision = s2Snapshot.decisions.find((d) => d.flow_id === selectedFlowId);

  // Selected flow's active paths for highlight
  const selectedPaths = s2Snapshot.allocation.results[selectedFlowId || '']?.paths || [];
  const highlightedArcs = selectedPaths.flatMap((p) => p.arcs);

  return (
    <div className="app-container" data-testid="app-root">
      {/* Top Navigation / Controls */}
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

          <div className="badge-seed" style={{ background: inFlight ? 'rgba(239, 68, 68, 0.15)' : 'rgba(16, 185, 129, 0.15)', color: inFlight ? '#f87171' : '#34d399' }}>
            <span>Step:</span>
            <strong>{activeStep}</strong>
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

      {/* Main Content */}
      <main className="dashboard-main">
        {/* Active Decision Banner */}
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
                  value={baselinePolicy}
                  onChange={(e) => setBaselinePolicy(e.target.value as 'S0-QoS' | 'S0')}
                >
                  <option value="S0-QoS">S0-QoS (Priority Queues)</option>
                  <option value="S0">S0 (Naive Dijkstra)</option>
                </select>
              </div>
            </div>

            <KpiStrip
              metrics={baselineSnapshot.metrics}
              policyName={baselinePolicy}
              label={activeStep > 0 ? 'Post-Failure (Overloaded)' : 'Steady State'}
            />

            <div className="graph-viewport-wrapper">
              <div className="graph-instruction-banner">Click any link to fail / recover</div>
              <TopologyGraph
                topology={topology}
                snapshot={baselineSnapshot}
                onLinkClick={handleLinkClick}
                highlightedArcs={highlightedArcs}
                highlightColor="#f59e0b"
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
              metrics={s2Snapshot.metrics}
              policyName="S2-Resilient"
              label={activeStep > 0 ? 'Capacity Protected' : 'Optimal Initial'}
            />

            <div className="graph-viewport-wrapper">
              <div className="graph-instruction-banner">Synchronized parallel view</div>
              <TopologyGraph
                topology={topology}
                snapshot={s2Snapshot}
                onLinkClick={handleLinkClick}
                highlightedArcs={highlightedArcs}
                highlightColor="#38bdf8"
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
          snapshot={s2Snapshot}
          selectedFlowId={selectedFlowId}
          onSelectFlow={setSelectedFlowId}
        />
      </main>
    </div>
  );
};

export default App;
