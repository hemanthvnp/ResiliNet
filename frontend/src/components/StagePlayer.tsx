import React from 'react';
import { Snapshot, Topology } from '../types/contract';

/**
 * Stage player for the last event (task 5.6): Before (the previous step), Link fails (the
 * previous routes drawn with the new link states) and Rerouted (the current step). A full
 * recompute has no intermediate state, so "Link fails" is a display composite of the two steps.
 */
export type Stage = 0 | 1 | 2;
export interface Pair {
  left: Snapshot;
  right: Snapshot;
}

/** The snapshot a panel shows at a stage, from the step before the event and the current one. */
export function stageSnapshot(stage: Stage, before: Snapshot, current: Snapshot): Snapshot {
  if (stage === 0) return before;
  if (stage === 1) return { ...before, step: current.step, link_state: current.link_state };
  return current;
}

/** Links whose state changed between the two steps, split by direction. */
export function changedLinks(before: Snapshot, current: Snapshot) {
  const ids = Object.keys(current.link_state)
    .filter((id) => before.link_state[id] !== current.link_state[id])
    .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
  return {
    failed: ids.filter((id) => current.link_state[id] === 'down'),
    recovered: ids.filter((id) => current.link_state[id] !== 'down'),
  };
}

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;

function linkNames(topology: Topology, ids: string[]) {
  const name = (id: string) => topology.nodes.find((n) => n.id === id)?.name ?? id;
  return ids
    .map((id) => {
      const l = topology.links.find((x) => x.id === id);
      return l ? `${id} (${name(l.u)} ↔ ${name(l.v)})` : id;
    })
    .join(', ');
}

function summary(s: Snapshot) {
  const k = s.metrics.overloaded_arcs;
  const over = k === 0 ? 'no link overloaded' : `${k} overloaded link${k === 1 ? '' : 's'} (max ${Math.round(s.metrics.max_util * 100)}%)`;
  return `${pct(s.metrics.dr)} delivered, ${over}`;
}

/** The caption for a stage, built only from the two steps' snapshots. */
export function stageCaption(stage: Stage, before: Pair, current: Pair, names: { left: string; right: string }, topology: Topology): string {
  if (stage === 0) {
    return `Before: ${names.left} delivers ${pct(before.left.metrics.dr)}, ${names.right} delivers ${pct(before.right.metrics.dr)}.`;
  }
  if (stage === 1) {
    const { failed, recovered } = changedLinks(before.right, current.right);
    if (failed.length === 0) return `${linkNames(topology, recovered)} ${recovered.length === 1 ? 'recovers' : 'recover'}.`;
    const affected = new Set([...current.left.affected_flows, ...current.right.affected_flows]).size;
    const it = failed.length === 1 ? 'it' : 'them';
    return (
      `${linkNames(topology, failed)} ${failed.length === 1 ? 'fails' : 'fail'}: ` +
      `${affected} flow${affected === 1 ? ' was' : 's were'} using ${it} (marked red). Routes are not yet recomputed.`
    );
  }
  return `Rerouted. ${names.left}: ${summary(current.left)}. ${names.right}: ${summary(current.right)}.`;
}

export const StagePlayer: React.FC<{
  stage: Stage | null;
  onStage: (stage: Stage | null) => void;
  caption: string;
  eventLabel: string;
}> = ({ stage, onStage, caption, eventLabel }) => (
  <div className="stage-player" data-testid="stage-player">
    <span className="stage-player-title">Replay the last event:</span>
    {(['Before', eventLabel, 'Rerouted'] as const).map((label, i) => (
      <button
        key={i}
        type="button"
        className={`btn-secondary ${stage === i ? 'btn-primary' : ''}`}
        onClick={() => onStage(i as Stage)}
        data-testid={`stage-${i + 1}`}
      >
        {i + 1} · {label}
      </button>
    ))}
    {stage !== null && (
      <button type="button" className="btn-secondary" onClick={() => onStage(null)} data-testid="stage-close">
        Back to current step
      </button>
    )}
    {stage !== null && (
      <div className="stage-caption" data-testid="stage-caption">
        {caption}
      </div>
    )}
  </div>
);
