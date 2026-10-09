import React from 'react';
import { DecisionRecord } from '../types/contract';

const dash = (v: number | null | undefined) => (v === null || v === undefined ? '—' : String(v));

export const DecisionPanel: React.FC<{ decision?: DecisionRecord }> = ({ decision }) => {
  if (!decision) return null;

  // PLAN.md section 10: the cut is the reason only when the greedy gap is 0
  const showCut = decision.cut.length > 0 && !((decision.greedy_gap ?? 0) > 0);

  return (
    <div className="decision-panel" data-testid="decision-panel">
      <div className="decision-explanation">{decision.explanation}</div>

      {decision.cause === 'DISCONNECTED' && (
        <div className="text-warning">Physically disconnected: no path exists with these links down</div>
      )}

      <div className="decision-facts font-mono">
        <span>Cause: {decision.cause}</span>
        <span>Reference: {decision.reference_status}</span>
        <span>Max-flow bound: {dash(decision.maxflow_bound)}</span>
        <span>Greedy gap: {dash(decision.greedy_gap)}</span>
      </div>

      {decision.attempts.length > 0 && (
        <table className="flow-table">
          <thead>
            <tr>
              <th>Attempt</th>
              <th>Arcs</th>
              <th>Bottleneck</th>
              <th>Pushed</th>
            </tr>
          </thead>
          <tbody>
            {decision.attempts.map((a) => (
              <tr key={a.iter}>
                <td className="font-mono">{a.iter}</td>
                <td className="font-mono">{a.arcs.join(', ')}</td>
                <td className="font-mono">{a.bottleneck}</td>
                <td className="font-mono">{a.pushed}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {showCut && (
        <ul className="decision-cut font-mono">
          {decision.cut.map((c) => (
            <li key={c.arc}>
              Cut {c.arc}: {c.state}
              {Object.entries(c.load_by_class)
                .map(([cls, load]) => ` · P${cls} ${load} Mbps`)
                .join('')}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
