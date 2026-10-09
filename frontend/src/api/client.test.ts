import { describe, it, expect, vi, afterEach } from 'vitest';
import { ApiClient } from './client';

function stubFetch(status: number, body: unknown, headers: Record<string, string> = {}) {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json', ...headers } }),
  );
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

describe('API client against the REST contract (Task 1.5)', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('creates a run with only scenario_id and policy (the API rejects unknown fields)', async () => {
    const fetchMock = stubFetch(200, { run_id: 'r1' });

    await new ApiClient('/api').createRun({ scenario_id: 'diamond', policy: 'S2' });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/runs');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual({ scenario_id: 'diamond', policy: 'S2' });
  });

  it('never sends the step of an event (the server assigns it)', async () => {
    const fetchMock = stubFetch(200, { step: 1 });

    await new ApiClient('/api').applyEvent('r1', { step: 7, kind: 'fail', links: ['L7'] } as never);

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/runs/r1/events');
    expect(JSON.parse(init.body)).toEqual({ kind: 'fail', links: ['L7'], node: null });
  });

  it('lists scenarios with a GET', async () => {
    const fetchMock = stubFetch(200, [{ id: 'diamond', name: 'Diamond', description: '' }]);

    const scenarios = await new ApiClient('/api').getScenarios();

    expect(fetchMock.mock.calls[0]).toEqual(['/api/scenarios', undefined]);
    expect(scenarios[0].id).toBe('diamond');
  });

  it("surfaces the API's error detail", async () => {
    stubFetch(422, { detail: "unknown link L99" });

    await expect(new ApiClient('/api').applyEvent('r1', { kind: 'fail', links: ['L99'] })).rejects.toThrow(
      'HTTP 422: unknown link L99',
    );
  });

  it('explains how to start the API when it cannot be reached', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));

    await expect(new ApiClient('/api').getScenarios()).rejects.toThrow('Start it with: uvicorn api.app:app --port 8000');
  });

  it('treats the dev proxy\'s empty 500 as a backend that is down', async () => {
    // What Vite's /api proxy answers when nothing listens on port 8000
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 500, statusText: 'Internal Server Error' })));

    await expect(new ApiClient('/api').getScenarios()).rejects.toThrow('Cannot reach the API at /api');
  });

  it("still reports the API's own JSON error for a 5xx", async () => {
    stubFetch(501, { detail: 'live mode needs core/sim' });

    await expect(new ApiClient('/api').getScenarios()).rejects.toThrow('HTTP 501: live mode needs core/sim');
  });

  it('records whether the API answered in mock mode', async () => {
    const client = new ApiClient('/api');
    stubFetch(200, [], { 'X-Mock': 'true' });
    await client.getScenarios();
    expect(client.mock).toBe(true);

    stubFetch(200, []);
    await client.getScenarios();
    expect(client.mock).toBe(false);
  });

  it('posts a comparison request', async () => {
    const fetchMock = stubFetch(200, { table: [] });

    await new ApiClient('/api').compare({ scenario_id: 'diamond', policies: ['S0-QoS', 'S2'] });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/compare');
    expect(JSON.parse(init.body)).toEqual({ scenario_id: 'diamond', policies: ['S0-QoS', 'S2'] });
  });
});
