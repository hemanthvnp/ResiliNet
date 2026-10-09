import React from 'react';
import { DecisionRecord, FlowResult } from '../types/contract';

const dash = (v: number | null | undefined) => (v === null || v === undefined ? '—' : String(v));
const mbps = (v: number) => String(Math.round(v * 100) / 100);

/** Node sequence of a path given as arc ids ("L7:B>D"). */
export const pathNodes = (arcs: string[]) => {
  const hops = arcs.map((a) => a.slice(a.indexOf(':') + 1).split('>'));
  return hops.length ? [hops[0][0], ...hops.map(([, v]) => v)].join('-') : '';
};

/**
 * `result` is the flow's allocation in the same panel's snapshot. Baseline records carry no
 * attempts, so their explanation stops at why the old path is invalid; the route actually taken
 * and what arrived come from the allocation.
 */
export const DecisionPanel: React.FC<{ decision?: DecisionRecord; result?: FlowResult }> = ({ decision, result }) => {
  if (!decision) return null;
  const baselineRoute = decision.attempts.length === 0 && result && result.paths.length > 0;

  // PLAN.md section 10: the cut is the reason only when the greedy gap is 0
  const showCut = decision.cut.length > 0 && !((decision.greedy_gap ?? 0) > 0);

  return (
    <div className="decision-panel" data-testid="decision-panel">
      <div className="decision-explanation">{decision.explanation}</div>

      {baselineRoute && (
        <div className="decision-explanation" data-testid="baseline-route">
          Routed on {result.paths.map((p) => pathNodes(p.arcs)).join(' and ')} with no capacity check:{' '}
          {mbps(result.delivered)} of {mbps(decision.demand)} Mbps delivered.
        </div>
      )}

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
