import React from 'react';
import { getLinkColor } from './TopologyGraph';

/** One legend for both panels, matching getLinkColor and getLinkLabel exactly (task 5.3). */
export const Legend: React.FC = () => (
  <div className="legend-strip" data-testid="legend">
    <div className="legend-item">
      <div
        className="legend-color-box legend-gradient"
        style={{
          background: `linear-gradient(90deg, ${getLinkColor(0, false)}, ${getLinkColor(0.5, false)}, ${getLinkColor(1, false)})`,
        }}
      />
      <span>Utilization 0% → 100% (labelled from 90%)</span>
    </div>
    <div className="legend-item">
      <div className="legend-color-box" style={{ background: getLinkColor(1.5, false) }} />
      <span>Overloaded, above 100% (labelled, e.g. 150%)</span>
    </div>
    <div className="legend-item">
      <div className="legend-color-box legend-dashed" style={{ background: getLinkColor(0, true) }} />
      <span>Failed: dashed, labelled DOWN</span>
    </div>
    <div className="legend-item">
      <span>Thicker line = more capacity · selected flow drawn in its class colour</span>
    </div>
    <div className="legend-item">
      <span>
        Moving dashes: the selected flow's computed Mbps along its routes, red where it is lost to
        overload (a fluid model, not individual packets)
      </span>
    </div>
  </div>
);
