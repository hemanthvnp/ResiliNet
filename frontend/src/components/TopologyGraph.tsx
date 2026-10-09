import React, { useEffect, useRef } from 'react';
import cytoscape, { Core, ElementDefinition, LayoutOptions } from 'cytoscape';
import { Topology, Snapshot } from '../types/contract';

export interface TopologyGraphProps {
  topology: Topology;
  snapshot: Snapshot;
  onLinkClick?: (linkId: string, currentStatus: 'up' | 'down') => void;
  highlightedArcs?: string[]; // e.g. ["L_DC_PRI:N_CORE1>N_DC"]
  highlightColor?: string;
  className?: string;
  readOnly?: boolean;
}

/**
 * Deterministic node coordinate generator.
 * Gives identical, stable positions for any topology with the same node list.
 */
export function getDeterministicPositions(topology: Topology): Record<string, { x: number; y: number }> {
  // Pre-mapped coordinates for known campus roles
  const campusLayout: Record<string, { x: number; y: number }> = {
    N_DC: { x: 400, y: 50 },
    N_CORE1: { x: 260, y: 160 },
    N_CORE2: { x: 540, y: 160 },
    N_DIST_N: { x: 200, y: 280 },
    N_DIST_S: { x: 600, y: 280 },
    N_CS_ENG: { x: 100, y: 400 },
    N_LIB: { x: 280, y: 400 },
    N_ADMIN: { x: 520, y: 400 },
    N_HOSTEL: { x: 700, y: 400 },
  };

  const positions: Record<string, { x: number; y: number }> = {};
  const sortedNodes = [...topology.nodes].sort((a, b) => a.id.localeCompare(b.id));

  sortedNodes.forEach((node, idx) => {
    if (campusLayout[node.id]) {
      positions[node.id] = { ...campusLayout[node.id] };
    } else {
      // Deterministic circle layout fallback for arbitrary topologies
      const angle = (2 * Math.PI * idx) / sortedNodes.length;
      const radius = 220;
      positions[node.id] = {
        x: 400 + Math.round(radius * Math.cos(angle)),
        y: 240 + Math.round(radius * Math.sin(angle)),
      };
    }
  });

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

export const TopologyGraph: React.FC<TopologyGraphProps> = ({
  topology,
  snapshot,
  onLinkClick,
  highlightedArcs = [],
  highlightColor = '#38bdf8',
  className = '',
  readOnly = false,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const positions = getDeterministicPositions(topology);

    const elements: ElementDefinition[] = [
      // Nodes
      ...topology.nodes.map((node) => ({
        group: 'nodes' as const,
        data: {
          id: node.id,
          label: node.name,
          type: node.type,
        },
        position: positions[node.id],
      })),
      // Edges
      ...topology.links.map((link) => {
        const isDown = snapshot.link_state[link.id] === 'down';
        const util = snapshot.metrics.link_util[link.id];
        const isHighlighted = highlightedArcs.some((arc) => arc.startsWith(`${link.id}:`));

        // Capacity scaled thickness: 2px (500M) to 7px (2000M)
        const width = Math.min(8, Math.max(2.5, Math.round((link.capacity / 2000) * 7)));

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
          },
        };
      }),
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
          },
        },
        {
          selector: 'edge:active',
          style: {
            'overlay-opacity': 0,
          },
        },
      ],
      layout: {
        name: 'preset',
      } as LayoutOptions,
      userZoomingEnabled: true,
      userPanningEnabled: true,
      boxSelectionEnabled: false,
      autoungrabify: true, // nodes locked in deterministic positions
    });

    if (!readOnly && onLinkClick) {
      cy.on('tap', 'edge', (evt) => {
        const edge = evt.target;
        const linkId = edge.id();
        const currentStatus = snapshot.link_state[linkId] === 'down' ? 'down' : 'up';
        onLinkClick(linkId, currentStatus);
      });
    }

    cyRef.current = cy;

    return () => {
      cy.destroy();
    };
  }, [topology, snapshot, highlightedArcs, highlightColor, readOnly, onLinkClick]);

  return (
    <div
      ref={containerRef}
      className={`topology-graph-container ${className}`}
      style={{ width: '100%', height: '100%', minHeight: '380px', position: 'relative' }}
      data-testid="topology-graph"
    />
  );
};
