import React, { useState } from 'react';
import { CartesianGrid, Legend as ChartLegend, Line, LineChart, Tooltip, XAxis, YAxis } from 'recharts';

/**
 * Benchmark chart (task 5.1): delivery ratio against offered load factor for S0-QoS and S2,
 * the mean over seeds, from the benchmark's long-format CSV (one row per seed, case, load
 * factor, policy and variant; add-cli-benchmark). Columns read: case, load_factor, policy,
 * variant, and the metric shown (dr, dr_p0 or dr_p1).
 */

export type BenchmarkRow = Record<string, string>;

const POLICIES = ['S0-QoS', 'S2'] as const;
const POLICY_COLORS: Record<string, string> = { 'S0-QoS': '#f59e0b', S2: '#38bdf8' };
export const METRICS = { dr: 'Total delivery (DR)', dr_p1: 'P1 academic delivery', dr_p0: 'P0 critical delivery' };
type Metric = keyof typeof METRICS;
const REQUIRED = ['case', 'load_factor', 'policy', 'variant', 'dr'];

/** Plain comma-separated values with a header row; the benchmark writes no quoted fields. */
export function parseBenchmarkCsv(text: string): BenchmarkRow[] {
  const [header, ...lines] = text.trim().split(/\r?\n/);
  const cols = header.split(',').map((c) => c.trim());
  const missing = REQUIRED.filter((c) => !cols.includes(c));
  if (missing.length) throw new Error(`benchmark CSV lacks column(s): ${missing.join(', ')}`);
  return lines
    .filter((l) => l.trim())
    .map((line) => {
      const cells = line.split(',');
      return Object.fromEntries(cols.map((c, i) => [c, (cells[i] ?? '').trim()]));
    });
}

/** Mean of `metric` over seeds, per load factor and policy, for one case and the default variant. */
export function chartData(rows: BenchmarkRow[], benchCase: string, metric: Metric) {
  const sums = new Map<number, Record<string, { total: number; n: number }>>();
  for (const r of rows) {
    if (r.case !== benchCase || r.variant !== 'default' || !(POLICIES as readonly string[]).includes(r.policy)) continue;
    const value = Number(r[metric]);
    if (r[metric] === undefined || r[metric] === '' || Number.isNaN(value)) continue;
    const lf = Number(r.load_factor);
    const byPolicy = sums.get(lf) ?? {};
    const acc = byPolicy[r.policy] ?? { total: 0, n: 0 };
    byPolicy[r.policy] = { total: acc.total + value, n: acc.n + 1 };
    sums.set(lf, byPolicy);
  }
  return [...sums.keys()]
    .sort((a, b) => a - b)
    .map((lf) => {
      const point: Record<string, number> = { load_factor: lf };
      for (const [policy, { total, n }] of Object.entries(sums.get(lf)!)) point[policy] = total / n;
      return point;
    });
}

export const BenchmarkChart: React.FC<{ rows: BenchmarkRow[]; source: string }> = ({ rows, source }) => {
  const cases = [...new Set(rows.map((r) => r.case))].sort();
  const [benchCase, setBenchCase] = useState(cases.includes('uplink') ? 'uplink' : cases[0]);
  const [metric, setMetric] = useState<Metric>('dr');
  const data = chartData(rows, benchCase, metric);
  const seeds = new Set(rows.filter((r) => r.case === benchCase).map((r) => r.seed)).size;

  return (
    <div className="panel-card benchmark-card" data-testid="benchmark-chart">
      <div className="panel-header">
        <span className="panel-title">Benchmark: {METRICS[metric]} against offered load</span>
        <select className="panel-selector" value={benchCase} onChange={(e) => setBenchCase(e.target.value)} aria-label="Benchmark case">
          {cases.map((c) => (
            <option key={c} value={c}>
              case: {c}
            </option>
          ))}
        </select>
        <select className="panel-selector" value={metric} onChange={(e) => setMetric(e.target.value as Metric)} aria-label="Benchmark metric">
          {Object.entries(METRICS).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>
      </div>
      <LineChart width={720} height={280} data={data} margin={{ top: 10, right: 24, bottom: 24, left: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
        <XAxis dataKey="load_factor" label={{ value: 'offered load factor', position: 'insideBottom', offset: -12 }} />
        <YAxis domain={[0, 1]} tickFormatter={(v: number) => `${Math.round(v * 100)}%`} />
        <Tooltip formatter={(v: number) => `${(v * 100).toFixed(1)}%`} />
        <ChartLegend verticalAlign="top" />
        {POLICIES.map((p) => (
          <Line key={p} type="monotone" dataKey={p} stroke={POLICY_COLORS[p]} strokeWidth={2} dot isAnimationActive={false} />
        ))}
      </LineChart>
      <div className="legend-strip">
        Mean over {seeds} seed{seeds === 1 ? '' : 's'}, default configuration. Source: {source}
      </div>
    </div>
  );
};
