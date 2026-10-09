import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { BenchmarkChart, chartData, parseBenchmarkCsv } from './BenchmarkChart';

// A small benchmark CSV, worked by hand: two seeds, two load factors, one ablation row that must be ignored
const CSV = `seed,case,load_factor,policy,variant,dr,dr_p0,dr_p1,compute_ms
0,uplink,0.5,S0-QoS,default,0.90,1.0,0.80,3.1
1,uplink,0.5,S0-QoS,default,0.80,1.0,0.70,2.9
0,uplink,0.5,S2,default,1.00,1.0,1.00,4.0
1,uplink,0.5,S2,default,0.96,1.0,0.90,4.2
0,uplink,1.5,S0-QoS,default,0.50,0.9,0.30,3.0
1,uplink,1.5,S0-QoS,default,0.40,0.8,0.20,3.0
0,uplink,1.5,S2,default,0.70,1.0,0.60,4.1
1,uplink,1.5,S2,default,0.60,1.0,0.50,4.1
0,uplink,1.5,S2,max_paths=1,0.10,0.1,0.10,4.1
0,healthy,0.5,S2,default,1.00,1.0,1.00,4.0
`;

describe('Benchmark chart (Task 5.1)', () => {
  it('averages each policy over seeds per load factor, default variant only', () => {
    const data = chartData(parseBenchmarkCsv(CSV), 'uplink', 'dr');

    expect(data.map((d) => d.load_factor)).toEqual([0.5, 1.5]);
    expect(data[0]['S0-QoS']).toBeCloseTo(0.85);
    expect(data[0].S2).toBeCloseTo(0.98);
    expect(data[1]['S0-QoS']).toBeCloseTo(0.45);
    expect(data[1].S2).toBeCloseTo(0.65); // the max_paths=1 ablation row is left out
  });

  it('charts another metric from the same rows', () => {
    const data = chartData(parseBenchmarkCsv(CSV), 'uplink', 'dr_p1');
    expect(data[1]['S0-QoS']).toBeCloseTo(0.25);
    expect(data[1].S2).toBeCloseTo(0.55);
  });

  it('names the columns a CSV is missing', () => {
    expect(() => parseBenchmarkCsv('seed,policy,dr\n0,S2,1')).toThrow('case, load_factor, variant');
  });

  it('renders with the uplink case selected by default', () => {
    render(<BenchmarkChart rows={parseBenchmarkCsv(CSV)} source="bench.csv" />);

    expect(screen.getByTestId('benchmark-chart')).toBeInTheDocument();
    expect((screen.getByLabelText('Benchmark case') as HTMLSelectElement).value).toBe('uplink');
    expect(screen.getByText(/Mean over 2 seeds/)).toBeInTheDocument();
  });
});
