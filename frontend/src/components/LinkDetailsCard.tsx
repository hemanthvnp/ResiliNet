import React from 'react';
import { Topology, Snapshot } from '../types/contract';

export interface LinkDetailsCardProps {
  linkId: string;
  topology: Topology;
  baselineSnapshot: Snapshot;
  s2Snapshot: Snapshot;
  baselinePolicy: string;
  onToggleStatus: (linkId: string, currentStatus: 'up' | 'down') => void;
  onClose: () => void;
  disabled?: boolean;
}

export const formatSpeed = (mbps: number): string => {
  if (mbps >= 1000) {
    return `${(mbps / 1000).toFixed(mbps % 1000 === 0 ? 0 : 1)} Gbps (${mbps} Mbps)`;
  }
  return `${mbps} Mbps`;
};

export const getUtilColor = (util: number, isDown: boolean): string => {
  if (isDown) return '#ef4444';
  if (util > 1.0) return '#d946ef'; // Overload (magenta/purple)
  if (util >= 0.9) return '#ef4444'; // Near saturation / saturated
  if (util >= 0.7) return '#f59e0b'; // Heavy
  return '#10b981'; // Healthy
};

export const LinkDetailsCard: React.FC<LinkDetailsCardProps> = ({
  linkId,
  topology,
  baselineSnapshot,
  s2Snapshot,
  baselinePolicy,
  onToggleStatus,
  onClose,
  disabled = false,
}) => {
  const link = topology.links.find((l) => l.id === linkId);
  if (!link) return null;

  const nodeName = (id: string) => topology.nodes.find((n) => n.id === id)?.name ?? id;
  const isDown = (s2Snapshot.link_state[linkId] ?? link.status) === 'down';

  // Capacity
  const capacity = link.capacity;

  // S2 metrics
  const s2Util = s2Snapshot.metrics.link_util[linkId] ?? 0;
  const s2Used = isDown ? 0 : Math.round(s2Util * capacity);
  const s2Free = isDown ? 0 : Math.max(0, capacity - s2Used);
  const s2Pct = isDown ? 0 : Math.round(s2Util * 100);

  // Baseline metrics
  const baseUtil = baselineSnapshot.metrics.link_util[linkId] ?? 0;
  const baseUsed = isDown ? 0 : Math.round(baseUtil * capacity);
  const baseFree = isDown ? 0 : Math.max(0, capacity - baseUsed);
  const basePct = isDown ? 0 : Math.round(baseUtil * 100);

  return (
    <div className="link-details-card" data-testid="link-details-card">
      <div className="link-details-header">
        <div className="link-details-title-group">
          <span className="link-details-badge-id">{link.id}</span>
          <span className="link-details-names">
            {nodeName(link.u)} ↔ {nodeName(link.v)}
          </span>
          <span
            className={`link-details-status-badge ${isDown ? 'status-down' : 'status-up'}`}
            data-testid="link-status-badge"
          >
            {isDown ? '● DOWN (FAILED)' : '● UP (ACTIVE)'}
          </span>
        </div>
        <button
          type="button"
          className="link-details-close-btn"
          onClick={onClose}
          aria-label="Close link details"
          data-testid="link-details-close"
        >
          ✕
        </button>
      </div>

      <div className="link-details-grid">
        {/* Capacity / Size Overview */}
        <div className="link-stat-box link-stat-capacity">
          <div className="link-stat-label">LINK CAPACITY (SIZE)</div>
          <div className="link-stat-value" data-testid="link-capacity-value">
            {formatSpeed(capacity)}
          </div>
          <div className="link-stat-sub">
            Latency: <strong>{link.latency} ms</strong>
          </div>
        </div>

        {/* S2 Usage (Our Policy) */}
        <div className="link-stat-box link-stat-policy s2-stat">
          <div className="link-stat-header">
            <span className="link-stat-label">S2 (RESILINET - OURS)</span>
            <span
              className="link-stat-pct"
              style={{ color: getUtilColor(s2Util, isDown) }}
              data-testid="s2-util-pct"
            >
              {isDown ? '0%' : `${s2Pct}%`}
            </span>
          </div>

          <div className="link-stat-value" data-testid="s2-used-value">
            {s2Used} <span className="unit">/ {capacity} Mbps</span>
          </div>

          {/* Progress bar */}
          <div className="link-progress-track">
            <div
              className="link-progress-fill"
              style={{
                width: `${Math.min(100, s2Pct)}%`,
                backgroundColor: getUtilColor(s2Util, isDown),
              }}
            />
          </div>

          <div className="link-stat-sub">
            {isDown ? (
              <span className="text-danger">Link down — 0 Mbps flowing</span>
            ) : (
              <span>
                Available Headroom: <strong>{s2Free} Mbps</strong>
              </span>
            )}
          </div>
        </div>

        {/* Baseline Usage */}
        <div className="link-stat-box link-stat-policy baseline-stat">
          <div className="link-stat-header">
            <span className="link-stat-label">BASELINE ({baselinePolicy})</span>
            <span
              className="link-stat-pct"
              style={{ color: getUtilColor(baseUtil, isDown) }}
              data-testid="baseline-util-pct"
            >
              {isDown ? '0%' : `${basePct}%`}
            </span>
          </div>

          <div className="link-stat-value" data-testid="baseline-used-value">
            {baseUsed} <span className="unit">/ {capacity} Mbps</span>
          </div>

          {/* Progress bar */}
          <div className="link-progress-track">
            <div
              className="link-progress-fill"
              style={{
                width: `${Math.min(100, basePct)}%`,
                backgroundColor: getUtilColor(baseUtil, isDown),
              }}
            />
          </div>

          <div className="link-stat-sub">
            {isDown ? (
              <span className="text-danger">Link down — 0 Mbps flowing</span>
            ) : basePct > 100 ? (
              <span className="text-danger">
                ⚠️ Overloaded by <strong>{baseUsed - capacity} Mbps</strong> ({basePct}%)
              </span>
            ) : (
              <span>
                Available Headroom: <strong>{baseFree} Mbps</strong>
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="link-details-actions">
        <button
          type="button"
          className={`btn-primary ${isDown ? 'btn-recover-action' : 'btn-fail-action'}`}
          onClick={() => onToggleStatus(link.id, isDown ? 'down' : 'up')}
          disabled={disabled}
          data-testid="link-toggle-btn"
        >
          {isDown ? '↺ Recover This Link' : '⚡ Fail This Link'}
        </button>
        <span className="link-details-tip">
          Tip: You can also toggle failure directly or inspect other links from the canvas.
        </span>
      </div>
    </div>
  );
};
