import React from 'react';
import { Flow, Snapshot } from '../types/contract';

// Route highlight colour per class; matches the .badge-p0/p1/p2 colours in index.css
export const CLASS_COLORS: Record<number, string> = { 0: '#f87171', 1: '#60a5fa', 2: '#a78bfa' };

export interface FlowTableProps {
  flows: Flow[];
  snapshot: Snapshot;
  selectedFlowId?: string | null;
  onSelectFlow?: (flowId: string) => void;
}

export const FlowTable: React.FC<FlowTableProps> = ({
  flows,
  snapshot,
  selectedFlowId,
  onSelectFlow,
}) => {
  // Sort deterministically: class ascending (P0, then P1, then P2), then flow ID
  const sortedFlows = [...flows].sort((a, b) => {
    if (a.cls !== b.cls) return a.cls - b.cls;
    return a.id.localeCompare(b.id, undefined, { numeric: true }); // F2 before F10
  });

  const getClassBadge = (cls: number) => {
    switch (cls) {
      case 0:
        return <span className="badge badge-p0">P0 Critical</span>;
      case 1:
        return <span className="badge badge-p1">P1 Academic</span>;
      case 2:
      default:
        return <span className="badge badge-p2">P2 Best Effort</span>;
    }
  };

  const getStatusBadge = (cause: string, delivered: number, demand: number) => {
    if (delivered >= demand) {
      return <span className="badge badge-success">Delivered</span>;
    }
    if (cause === 'OVERLOAD_LOSS') {
      return <span className="badge badge-danger">Overload Loss</span>;
    }
    if (cause === 'INSUFFICIENT_CAPACITY') {
      return <span className="badge badge-warning">Cap Limit</span>;
    }
    if (cause === 'DISCONNECTED') {
      return <span className="badge badge-danger">Disconnected</span>;
    }
    return <span className="badge badge-neutral">{cause}</span>;
  };

  return (
    <div className="flow-table-container" data-testid="flow-table">
      <div className="table-header-title">Active Traffic Demands ({flows.length})</div>
      <div className="table-wrapper">
        <table className="flow-table">
          <thead>
            <tr>
              <th>Flow ID</th>
              <th>Class</th>
              <th>Service</th>
              <th>Demand</th>
              <th>Delivered</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {sortedFlows.map((flow) => {
              const result = snapshot.allocation.results[flow.id];
              const delivered = result ? result.delivered : flow.rate;
              const cause = result ? result.cause : 'NONE';
              const isSelected = selectedFlowId === flow.id;

              return (
                <tr
                  key={flow.id}
                  className={`flow-row ${isSelected ? 'row-selected' : ''}`}
                  onClick={() => onSelectFlow && onSelectFlow(flow.id)}
                >
                  <td className="font-mono">{flow.id}</td>
                  <td>{getClassBadge(flow.cls)}</td>
                  <td>{flow.service || `${flow.src} → ${flow.dst}`}</td>
                  <td className="font-mono">{flow.rate} Mbps</td>
                  <td className="font-mono">
                    <span className={delivered < flow.rate ? 'text-warning' : 'text-success'}>
                      {delivered.toFixed(0)} Mbps
                    </span>
                  </td>
                  <td>{getStatusBadge(cause, delivered, flow.rate)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
