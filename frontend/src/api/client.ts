import {
  CompareResponse,
  DecisionRecord,
  EventRequest,
  PolicyConfig,
  RunResponse,
  ScenarioInfo,
  Snapshot,
} from '../types/contract';

export type Policy = 'S0' | 'S0-QoS' | 'S1' | 'S2';

/**
 * Typed client for the REST API (api/app.py). There is no client-side mock: for offline
 * development run the API in mock mode (REROUTER_MOCK=1 uvicorn api.app:app), so the UI
 * always talks to one contract.
 */
export class ApiClient {
  /** True when the last answer came from the API's mock mode (header X-Mock: true): fixtures, not simulation. */
  mock = false;

  constructor(private baseUrl: string = '/api') {}

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    let res: Response;
    try {
      res = await fetch(`${this.baseUrl}${path}`, init);
    } catch {
      throw new Error(
        `Cannot reach the API at ${this.baseUrl}. Start it with: REROUTER_MOCK=1 uvicorn api.app:app --reload`,
      );
    }
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const parsed = await res.json();
        detail = typeof parsed.detail === 'string' ? parsed.detail : JSON.stringify(parsed.detail);
      } catch {
        // no JSON body: keep the status text
      }
      throw new Error(`HTTP ${res.status}: ${detail}`);
    }
    this.mock = res.headers.get('X-Mock') === 'true';
    return res.json();
  }

  private post<T>(path: string, body: unknown = {}): Promise<T> {
    return this.request(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  }

  getScenarios(): Promise<ScenarioInfo[]> {
    return this.request('/scenarios');
  }

  createRun(params: { scenario_id: string; policy: Policy; config?: PolicyConfig }): Promise<RunResponse> {
    return this.post('/runs', params);
  }

  applyEvent(runId: string, event: EventRequest): Promise<Snapshot> {
    // Built field by field so a stored Event's `step` is never sent.
    return this.post(`/runs/${runId}/events`, { kind: event.kind, links: event.links, node: event.node ?? null });
  }

  resetRun(runId: string): Promise<Snapshot> {
    return this.post(`/runs/${runId}/reset`);
  }

  compare(params: { scenario_id: string; policies: Policy[]; config?: PolicyConfig }): Promise<CompareResponse> {
    return this.post('/compare', params);
  }

  getDecision(runId: string, flowId: string): Promise<DecisionRecord> {
    return this.request(`/runs/${runId}/flows/${flowId}/decision`);
  }
}

export const apiClient = new ApiClient();
