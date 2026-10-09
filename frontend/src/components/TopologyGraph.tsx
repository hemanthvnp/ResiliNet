import React, { useEffect, useRef, useState } from 'react';
import cytoscape, { Core, ElementDefinition, LayoutOptions } from 'cytoscape';
import { Topology, Snapshot } from '../types/contract';

export interface ViewportState {
  zoom: number;
  pan: { x: number; y: number };
}

export interface TopologyGraphProps {
  topology: Topology;
  snapshot: Snapshot;
  onLinkClick?: (linkId: string, currentStatus: 'up' | 'down') => void;
  highlightedArcs?: string[]; // e.g. ["L_DC_PRI:N_CORE1>N_DC"]
  highlightColor?: string;
  className?: string;
  readOnly?: boolean;
  viewport?: ViewportState;
  onViewportChange?: (viewport: ViewportState) => void;
}

// Rows of the campus hierarchy, top to bottom; a type not listed here goes on a last row.
const LAYER_OF_TYPE: Record<string, number> = {
  service: 0,
  core: 1,
  distribution: 2,
  building: 3,
  access: 3,
  hostel: 3,
};
const WIDTH = 800;
const ROW_GAP = 120;
const MAX_PER_ROW = 12;
const LABEL_ALL_UP_TO = 20; // above this many nodes, building labels overlap and only the backbone is named

/** A node's label: every node on a small network, only services, core and distribution on a large one. */
export function getNodeLabel(node: { name: string; type: string }, nodeCount: number): string {
  return nodeCount <= LABEL_ALL_UP_TO || (LAYER_OF_TYPE[node.type] ?? 4) < 3 ? node.name : '';
} // a wider layer (e.g. 37 generated buildings) wraps onto further rows

/**
 * Deterministic node coordinates: nodes are placed in rows by type (services, core,
 * distribution, then buildings and hostels), sorted by id within a row and spread evenly.
 * A topology whose nodes all share one row (e.g. the diamond) is drawn on a circle instead.
 */
export function getDeterministicPositions(topology: Topology): Record<string, { x: number; y: number }> {
  // numeric-aware, so generated ids run N2, N3 ... N10 rather than N10, N11, N2
  const sortedNodes = [...topology.nodes].sort((a, b) => a.id.localeCompare(b.id, undefined, { numeric: true }));
  const layerOf = (type: string) => LAYER_OF_TYPE[type] ?? 4;
  const rows = new Map<number, string[]>();
  for (const node of sortedNodes) {
    const layer = layerOf(node.type);
    rows.set(layer, [...(rows.get(layer) ?? []), node.id]);
  }

  const positions: Record<string, { x: number; y: number }> = {};
  if (rows.size <= 1) {
    sortedNodes.forEach((node, idx) => {
      const angle = (2 * Math.PI * idx) / sortedNodes.length;
      positions[node.id] = {
        x: WIDTH / 2 + Math.round(220 * Math.cos(angle)),
        y: 240 + Math.round(220 * Math.sin(angle)),
      };
    });
    return positions;
  }

  let rowIdx = 0;
  for (const layer of [...rows.keys()].sort((a, b) => a - b)) {
    const ids = rows.get(layer)!;
    for (let start = 0; start < ids.length; start += MAX_PER_ROW, rowIdx++) {
      const row = ids.slice(start, start + MAX_PER_ROW);
      row.forEach((id, i) => {
        positions[id] = { x: Math.round(((i + 1) * WIDTH) / (row.length + 1)), y: 60 + rowIdx * ROW_GAP };
      });
    }
  }
  return positions;
}

/**
 * Calculates edge color based on link utilization according to PLAN.md section 7 & 10.
 * Sequential green -> yellow -> red for 0..1, distinct overload color (magenta) for > 1.0.
 */
export function getLinkLineStyle(isDown: boolean): 'dashed' | 'solid' {
  return isDown ? 'dashed' : 'solid';
}

export function getLinkColor(util: number | undefined, isDown: boolean): string {
  if (isDown) return '#ef4444'; // Red for down/failed
  if (util === undefined) return '#10b981';
  if (util > 1.0) return '#d946ef'; // Overload color (fuchsia/magenta)

  // Sequential Green (#10b981) -> Amber (#f59e0b) -> Red (#ef4444)
  if (util <= 0.5) {
    const t = util / 0.5;
    return interpolateColor('#10b981', '#f59e0b', t);
  } else {
    const t = (util - 0.5) / 0.5;
    return interpolateColor('#f59e0b', '#ef4444', t);
  }
}

function interpolateColor(color1: string, color2: string, factor: number): string {
  const c1 = parseInt(color1.slice(1), 16);
  const c2 = parseInt(color2.slice(1), 16);

  const r1 = (c1 >> 16) & 255;
  const g1 = (c1 >> 8) & 255;
  const b1 = c1 & 255;

  const r2 = (c2 >> 16) & 255;
  const g2 = (c2 >> 8) & 255;
  const b2 = c2 & 255;

  const r = Math.round(r1 + factor * (r2 - r1));
  const g = Math.round(g1 + factor * (g2 - g1));
  const b = Math.round(b1 + factor * (b2 - b1));

  return `#${((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1)}`;
}

/** Cytoscape edge data per link; a link on any highlighted arc takes the highlight colour. */
/**
 * Text on the edge, so a failed link, a full link and an overloaded one can be told apart
 * without colour (a link at 100% and a failed link are both red; task 5.3).
 */
export function getLinkLabel(util: number | undefined, isDown: boolean): string {
  if (isDown) return 'DOWN';
  if (util !== undefined && util >= 0.9) return `${Math.round(util * 100)}%`;
  return '';
}

/** The hint shown while the mouse is over a link, e.g. "Click to fail L6: Core 1 ↔ Distribution 1". */
export function getLinkHint(topology: Topology, snapshot: Snapshot, linkId: string): string {
  const link = topology.links.find((l) => l.id === linkId);
  if (!link) return '';
  const name = (id: string) => topology.nodes.find((n) => n.id === id)?.name ?? id;
  const verb = snapshot.link_state[linkId] === 'down' ? 'recover' : 'fail';
  return `Click to ${verb} ${linkId}: ${name(link.u)} ↔ ${name(link.v)} (${link.capacity} Mbps)`;
}

export const ZOOM_STEP = 1.3;

export function getEdgeElements(
  topology: Topology,
  snapshot: Snapshot,
  highlightedArcs: string[],
  highlightColor: string,
): ElementDefinition[] {
  return topology.links.map((link) => {
    const isDown = snapshot.link_state[link.id] === 'down';
    const util = snapshot.metrics.link_util[link.id];
    const isHighlighted = highlightedArcs.some((arc) => arc.startsWith(`${link.id}:`));

    // Capacity scaled thickness: 2px (500M) to 7px (2000M)
    // at least 3.5 px, so a line is easy to hit with the mouse when the campus is zoomed out
    const width = Math.min(8, Math.max(3.5, Math.round((link.capacity / 2000) * 7)));

    return {
      group: 'edges' as const,
      data: {
        id: link.id,
        source: link.u,
        target: link.v,
        capacity: link.capacity,
        latency: link.latency,
        status: isDown ? 'down' : 'up',
        util: util !== undefined ? (util * 100).toFixed(0) : '0',
        color: isHighlighted ? highlightColor : getLinkColor(util, isDown),
        lineStyle: isDown ? 'dashed' : 'solid',
        width: isHighlighted ? width + 2 : width,
        label: getLinkLabel(util, isDown),
      },
    };
  });
}

export const TopologyGraph: React.FC<TopologyGraphProps> = ({
  topology,
  snapshot,
  onLinkClick,
  highlightedArcs = [],
  highlightColor = '#38bdf8',
  className = '',
  readOnly = false,
  viewport,
  onViewportChange,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const [hint, setHint] = useState('');
  // The latest callbacks, read through refs: App passes new functions on every render, and
  // having them in the build effect's dependencies rebuilt the graph mid-drag, so panning
  // by dragging did nothing.
  const onLinkClickRef = useRef(onLinkClick);
  onLinkClickRef.current = onLinkClick;
  const onViewportChangeRef = useRef(onViewportChange);
  onViewportChangeRef.current = onViewportChange;

  // Zoom about the centre of the view; the 'zoom' event then syncs the partner panel
  const zoomBy = (factor: number) => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.zoom({ level: cy.zoom() * factor, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } });
  };
  const fitView = () => cyRef.current?.fit(undefined, 24);

  useEffect(() => {
    if (!containerRef.current) return;

    const positions = getDeterministicPositions(topology);

    const elements: ElementDefinition[] = [
      // Nodes
      ...topology.nodes.map((node) => ({
        group: 'nodes' as const,
        data: {
          id: node.id,
          label: getNodeLabel(node, topology.nodes.length),
          type: node.type,
        },
        position: positions[node.id],
      })),
      ...getEdgeElements(topology, snapshot, highlightedArcs, highlightColor),
    ];

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: 'node',
          style: {
            'label': 'data(label)',
            'color': '#cbd5e1',
            'font-family': 'Inter, sans-serif',
            'font-size': '11px',
            'font-weight': 500 as any,
            'text-valign': 'bottom',
            'text-margin-y': 6,
            'background-color': '#1e293b',
            'border-width': 2,
            'border-color': '#64748b',
            'width': 34,
            'height': 34,
            'overlay-opacity': 0,
          },
        },
        {
          selector: 'node[type = "core"]',
          style: {
            'background-color': '#0284c7',
            'border-color': '#38bdf8',
            'width': 40,
            'height': 40,
          },
        },
        {
          selector: 'node[type = "service"]',
          style: {
            'background-color': '#7c3aed',
            'border-color': '#a855f7',
            'width': 42,
            'height': 42,
          },
        },
        {
          selector: 'node[type = "access"]',
          style: {
            'background-color': '#0f766e',
            'border-color': '#14b8a6',
          },
        },
        {
          selector: 'edge',
          style: {
            'width': 'data(width)' as any,
            'line-color': 'data(color)' as any,
            'line-style': 'data(lineStyle)' as any,
            'curve-style': 'bezier',
            'opacity': 0.88,
            'target-arrow-shape': 'none',
            'underlay-color': '#38bdf8',
            'underlay-padding': 6,
            'underlay-opacity': 0,
            'label': 'data(label)',
            'font-size': '10px',
            'font-weight': 700 as any,
            'color': '#f8fafc',
            'text-background-color': '#0f172a',
            'text-background-opacity': 0.85,
            'text-background-padding': '2px' as any,
            'text-events': 'yes', // a click on a "DOWN" or "225%" label counts as a click on its link
          },
        },
        {
          selector: 'edge.hovered',
          style: {
            'underlay-opacity': 0.45,
            'underlay-padding': 8,
            'z-index': 10,
          },
        },
        {
          selector: 'edge:active',
          style: {
            'overlay-opacity': 0.2,
            'overlay-color': '#ef4444',
          },
        },
      ],
      layout: {
        name: 'preset',
      } as LayoutOptions,
      userZoomingEnabled: true,
      userPanningEnabled: true,
      wheelSensitivity: 3, // the default zooms about 5% per scroll, too little to be useful
      minZoom: 0.3,
      maxZoom: 4,
      boxSelectionEnabled: false,
      autoungrabify: true, // nodes locked in deterministic positions
    });

    if (!readOnly && onLinkClickRef.current) {
      cy.on('mouseover', 'edge', (evt) => {
        if (containerRef.current) containerRef.current.style.cursor = 'pointer';
        evt.target.addClass('hovered');
        setHint(getLinkHint(topology, snapshot, evt.target.id()));
      });
      cy.on('mouseout', 'edge', (evt) => {
        if (containerRef.current) containerRef.current.style.cursor = 'default';
        evt.target.removeClass('hovered');
        setHint('');
      });

      cy.on('tap', 'edge', (evt) => {
        const edge = evt.target;
        const linkId = edge.id();
        const currentStatus = snapshot.link_state[linkId] === 'down' ? 'down' : 'up';
        onLinkClickRef.current?.(linkId, currentStatus);
      });
    }

    // Synchronized pan/zoom event dispatch
    // Cytoscape pans when a drag starts on the background or on a link, but not on a node (nodes
    // are locked). On a dense campus a drag that starts on a node then does nothing, so it pans
    // the view by hand.
    let dragFrom: { x: number; y: number } | null = null;
    cy.on('tapstart', 'node', (evt) => {
      dragFrom = { ...evt.renderedPosition };
    });
    cy.on('tapdrag', (evt) => {
      if (!dragFrom) return;
      const to = evt.renderedPosition;
      cy.panBy({ x: to.x - dragFrom.x, y: to.y - dragFrom.y });
      dragFrom = { ...to };
    });
    cy.on('tapend', () => {
      dragFrom = null;
    });

    cy.on('pan zoom', () => {
      const curPan = cy.pan();
      onViewportChangeRef.current?.({ zoom: cy.zoom(), pan: { x: curPan.x, y: curPan.y } });
    });

    // Apply external viewport if provided
    if (viewport) {
      cy.viewport({ zoom: viewport.zoom, pan: viewport.pan });
    }

    cyRef.current = cy;

    return () => {
      cy.destroy();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- callbacks are read through refs;
    // highlightedArcs is compared by value, since App builds a new array on every render
  }, [topology, snapshot, highlightedArcs.join(','), highlightColor, readOnly]);

  // Re-fit when the container changes size (switching to Stacked or Toggle, or resizing the
  // window): cytoscape does not notice on its own and keeps the old, smaller drawing.
  useEffect(() => {
    const el = containerRef.current;
    if (!el || typeof ResizeObserver === 'undefined') return;
    let last = { w: el.clientWidth, h: el.clientHeight };
    const observer = new ResizeObserver(() => {
      const cy = cyRef.current;
      const size = { w: el.clientWidth, h: el.clientHeight };
      if (!cy || (size.w === last.w && size.h === last.h)) return;
      last = size;
      cy.resize();
      cy.fit(undefined, 24);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Synchronize viewport updates when received from partner panel
  useEffect(() => {
    if (!cyRef.current || !viewport) return;
    const cy = cyRef.current;
    const currentZoom = cy.zoom();
    const currentPan = cy.pan();

    // Only update if difference exceeds threshold to avoid jitter
    if (
      Math.abs(currentZoom - viewport.zoom) > 0.001 ||
      Math.abs(currentPan.x - viewport.pan.x) > 1 ||
      Math.abs(currentPan.y - viewport.pan.y) > 1
    ) {
      cy.viewport({ zoom: viewport.zoom, pan: viewport.pan });
    }
  }, [viewport]);

  return (
    <div className="topology-graph-wrap">
      <div
        ref={containerRef}
        className={`topology-graph-container ${className}`}
        style={{ width: '100%', height: '100%', position: 'relative' }} // min-height in .topology-graph-container (index.css)
        data-testid="topology-graph"
      />
      {hint && (
        <div className="graph-hover-hint" data-testid="graph-hover-hint">
          {hint}
        </div>
      )}
      <div className="graph-zoom-controls">
        <button type="button" onClick={() => zoomBy(ZOOM_STEP)} aria-label="Zoom in">+</button>
        <button type="button" onClick={() => zoomBy(1 / ZOOM_STEP)} aria-label="Zoom out">−</button>
        <button type="button" onClick={fitView} aria-label="Fit to view">Fit</button>
      </div>
    </div>
  );
};
