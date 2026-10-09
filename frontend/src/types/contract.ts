/**
 * Contract types, generated from the committed OpenAPI schema (api/openapi.json), which the API
 * generates from core/model/types.py and api/schemas.py. Do not hand-edit these: change the
 * backend, run `npm run generate-client`, and the compiler shows every place the UI must follow.
 */
import type { components } from './openapi.gen';

type S = components['schemas'];

export type Node = S['Node'];
export type Link = S['Link'];
export type LinkStatus = Link['status'];
export type Topology = S['Topology'];
export type Flow = S['Flow'];
export type PathAlloc = S['PathAlloc'];
export type FlowResult = S['FlowResult'];
export type FlowCause = FlowResult['cause'];
export type Allocation = S['Allocation'];
export type PolicyConfig = S['PolicyConfig'];
export type Event = S['Event'];
export type Attempt = S['Attempt'];
export type CutArc = S['CutArc'];
export type DecisionRecord = S['DecisionRecord'];
export type Metrics = S['Metrics'];
export type Snapshot = S['Snapshot'];
export type TemplateTopologySpec = S['TemplateTopologySpec'];
export type GeneratedTopologySpec = S['GeneratedTopologySpec'];
export type TopologySpec = Scenario['topology'];
export type GeneratedTrafficSpec = S['GeneratedTrafficSpec'];
export type TrafficSpec = Scenario['traffic'];
export type Scenario = S['Scenario'];

// API envelopes (api/schemas.py)
export type ScenarioInfo = S['ScenarioInfo'];
export type RunResponse = S['RunResponse'];
export type EventRequest = S['EventRequest'];
export type CompareRow = S['CompareRow'];
export type CompareResponse = S['CompareResponse'];
