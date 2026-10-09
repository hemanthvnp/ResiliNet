import React from 'react';
import { Metrics } from '../types/contract';

export interface KpiStripProps {
  metrics: Metrics;
  label?: string;
  policyName?: string;
}

// Fixed display order specified in PLAN.md Section 10 and Task 3.4
export const CAUSE_DISPLAY_ORDER = [
  'INSUFFICIENT_CAPACITY',
  'DISCONNECTED',
  'PATH_LIMIT',
  'OVERLOAD_LOSS',
] as const;

export const CAUSE_LABELS: Record<string, string> = {
  INSUFFICIENT_CAPACITY: 'Capacity',
  DISCONNECTED: 'Disconnected',
  PATH_LIMIT: 'Path Limit',
  OVERLOAD_LOSS: 'Overload Loss',
};

export const KpiStrip: React.FC<KpiStripProps> = ({ metrics, label, policyName }) => {
  const drPercent = (metrics.dr * 100).toFixed(1);
  const drP0Percent = ((metrics.dr_by_class[0] ?? 1.0) * 100).toFixed(1);
  const drP1Percent = ((metrics.dr_by_class[1] ?? 1.0) * 100).toFixed(1);

  const isOverloaded = metrics.overloaded_arcs > 0;
  const maxUtilPercent = (metrics.max_util * 100).toFixed(0);

  // Calculate unserved traffic totals
  const unservedCauses = metrics.unserved_by_cause || {};

  return (
    <div className="kpi-strip-card" data-testid="kpi-strip">
      <div className="kpi-strip-header">
        <span className="policy-badge">{policyName || 'Policy'}</span>
        {label && <span className="kpi-label">{label}</span>}
      </div>

      <div className="kpi-metrics-grid">
        <div className="kpi-item">
          <div className="kpi-title">Delivery (DR)</div>
          <div className="kpi-value text-accent">{drPercent}%</div>
        </div>

        <div className="kpi-item">
          <div className="kpi-title">P0 Critical</div>
          <div className={`kpi-value ${metrics.dr_by_class[0] < 1.0 ? 'text-danger' : 'text-success'}`}>
            {drP0Percent}%
          </div>
        </div>

        <div className="kpi-item">
          <div className="kpi-title">P1 Academic</div>
          <div className={`kpi-value ${metrics.dr_by_class[1] < 1.0 ? 'text-warning' : 'text-success'}`}>
            {drP1Percent}%
          </div>
        </div>

        <div className="kpi-item">
          <div className="kpi-title">Overloaded Links</div>
          <div className={`kpi-value ${isOverloaded ? 'text-overload animate-pulse' : 'text-neutral'}`}>
            {metrics.overloaded_arcs}
          </div>
        </div>

        <div className="kpi-item">
          <div className="kpi-title">Max Utilization</div>
          <div className={`kpi-value ${metrics.max_util > 1.0 ? 'text-overload' : 'text-neutral'}`}>
            {maxUtilPercent}%
          </div>
        </div>
      </div>

      {/* Unserved traffic breakdown in fixed order (Task 3.4) */}
      <div className="kpi-unserved-causes" data-testid="unserved-causes">
        <span className="unserved-caption">Unserved by Cause:</span>
        <div className="causes-list">
          {CAUSE_DISPLAY_ORDER.map((causeKey) => {
            const amount = unservedCauses[causeKey] || 0;
            return (
              <span
                key={causeKey}
                className={`cause-tag ${amount > 0 ? 'cause-active' : 'cause-zero'}`}
                data-testid={`cause-${causeKey}`}
              >
                {CAUSE_LABELS[causeKey]}: <strong>{amount} Mbps</strong>
              </span>
            );
          })}
        </div>
      </div>
    </div>
  );
};
