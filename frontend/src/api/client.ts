import { Scenario, Snapshot, Event } from '../types/contract';
import { CAMPUS_TOPOLOGY, INITIAL_FLOWS, MOCK_STEP0_SNAPSHOT, MOCK_STEP1_S2_SNAPSHOT, MOCK_STEP1_S0_QOS_SNAPSHOT } from '../fixtures/mockData';

export interface ApiClientConfig {
  baseUrl?: string;
  useMock?: boolean;
}

export class ApiClient {
  private baseUrl: string;
  private useMock: boolean;

  constructor(config: ApiClientConfig = {}) {
    this.baseUrl = config.baseUrl || '/api';
    this.useMock = config.useMock !== undefined ? config.useMock : true;
  }

  setMockMode(enable: boolean) {
    this.useMock = enable;
  }

  isMockMode(): boolean {
    return this.useMock;
  }

  async getScenarios(): Promise<Scenario[]> {
    if (this.useMock) {
      return [
        {
          id: 'campus-template',
          name: 'Campus Backbone (Default)',
          seed: 42,
          topology: CAMPUS_TOPOLOGY,
          flows: INITIAL_FLOWS,
          events: [{ step: 1, kind: 'fail', links: ['L_DC_PRI'] }],
          config: { order: 'class_size_desc', max_paths: 3, congestion_lambda: 0, util_cap: 1.0 },
        },
      ];
    }
    const res = await fetch(`${this.baseUrl}/scenarios`);
    if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to fetch scenarios`);
    return res.json();
  }

  async createRun(params: { scenario_id?: string; policy: 'S0' | 'S0-QoS' | 'S1' | 'S2'; seed?: number }): Promise<{ run_id: string; snapshot: Snapshot }> {
    if (this.useMock) {
      return {
        run_id: `run-${params.policy.toLowerCase()}-${Date.now()}`,
        snapshot: JSON.parse(JSON.stringify(MOCK_STEP0_SNAPSHOT)),
      };
    }
    const res = await fetch(`${this.baseUrl}/runs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to create run`);
    return res.json();
  }

  async applyEvent(runId: string, event: Omit<Event, 'step'>, policy?: string): Promise<Snapshot> {
    if (this.useMock) {
      const isS0 = policy === 'S0' || policy === 'S0-QoS';
      if (event.kind === 'fail' && event.links.includes('L_DC_PRI')) {
        return JSON.parse(JSON.stringify(isS0 ? MOCK_STEP1_S0_QOS_SNAPSHOT : MOCK_STEP1_S2_SNAPSHOT));
      }
      return JSON.parse(JSON.stringify(MOCK_STEP0_SNAPSHOT));
    }
    const res = await fetch(`${this.baseUrl}/runs/${runId}/events`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(event),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to apply event`);
    return res.json();
  }

  async resetRun(runId: string): Promise<Snapshot> {
    if (this.useMock) {
      return JSON.parse(JSON.stringify(MOCK_STEP0_SNAPSHOT));
    }
    const res = await fetch(`${this.baseUrl}/runs/${runId}/reset`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to reset run`);
    return res.json();
  }
}

export const apiClient = new ApiClient();
