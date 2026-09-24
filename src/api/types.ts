import type { Assignment, Decision, PlanningConstraint, Scenario, VerificationReport } from '../types'

export type FeedState = 'ok' | 'stale' | 'failing' | 'no_data'

export interface FeedHealth {
  source: 'sachet' | 'usgs' | 'gdacs'
  state: FeedState
  last_ok_at: string | null
  last_poll_at: string | null
  last_error: string | null
  interval_min: number
}

export interface StatusResponse {
  server_time: string
  feeds: FeedHealth[]
  model: { configured: boolean; model: string; provider: string }
  pending_approvals: number
  exercise: { id: string; name: string; started_at: string | null } | null
}

export interface DecisionSummary {
  decision_id: number
  scenario_id: string
  engine: string
  status: 'requires_human_approval' | 'blocked'
  coverage: number
  proposer_sub: string | null
  created_at: string | null
  blocking_check_ids: string[]
  disposition: { action: 'approve' | 'reject'; actor: string; timestamp: string | null } | null
}

export interface AuditEvent {
  id: number
  ts: string
  actor: string
  type: string
  payload: Record<string, unknown>
  prev_hash: string
  hash: string
}

export interface Labels {
  incidents: Record<string, string | null>
  units: Record<string, string | null>
}

export interface TravelTimeMatrix {
  provider: string
  minutes: Record<string, Record<string, number>>
  degraded: boolean
  degraded_reason: string | null
}

/** GET /api/v1/decisions/{id}: the stored record. */
export interface StoredDecision extends Decision {
  scenario: Scenario
  scenario_sha256: string
  proposer_sub: string | null
  created_at: string
  travel_times: TravelTimeMatrix
  constraints: PlanningConstraint[]
  evidence: { id: string; description: string; source: string; confidence: number }[]
  constraint_sources: ({ note: string; quote: string | null } | null)[]
  traceparent: string | null
  approvals: { disposition_id: number; action: 'approve' | 'reject'; reason_code: string | null; actor: string; timestamp: string }[]
}

export type { Assignment }

export interface RouteGeometry {
  resource_id: string
  incident_id: string
  coordinates: [number, number][] // [lon, lat]
  geometry: 'road' | 'straight_line'
  reason: string | null
}

export interface AlertArea {
  area_desc: string | null
  polygons: [number, number][][] // [lat, lon] rings (CAP order)
  circles: [number, number, number][] // lat, lon, radius km
}

export interface AlertSummary {
  source: 'sachet' | 'usgs' | 'gdacs'
  identifier: string
  sent_at: string | null
  fetched_at: string
  event: string | null
  severity: string | null
  headline: string | null
  area_desc: string | null
  location: { lat: number; lon: number } | null
  areas: AlertArea[]
}

export interface Baseline {
  decision_id: number
  constraints: number
  status: string
  assignments: Assignment[]
  unmet_requirements: Decision['unmet_requirements']
  objective: number
  plan_objective: number
  only_in_plan: { incident_id: string; resource_id: string }[]
  only_in_baseline: { incident_id: string; resource_id: string }[]
  same_as_plan: boolean
}

export interface Reverification {
  decision_id: number
  matches: boolean
  same_verdict: boolean
  differing_checks: string[]
  stored: VerificationReport
  recomputed: VerificationReport
  scenario_sha256: string
  scenario_sha256_matches: boolean
  event_id: number
}

export type ReasonCodes = Record<'approve' | 'reject', Record<string, string>>

export interface DispositionResult {
  decision_id: number
  disposition_id: number
  action: 'approve' | 'reject'
  reason_code: string
  timestamp: string
}

export const SIGNALS = [
  'trapped', 'injured', 'unconscious', 'drowning', 'electrocution', 'collapse',
  'fire_spreading', 'water_rising', 'missing_person', 'medical_emergency',
] as const
export type Signal = (typeof SIGNALS)[number]

interface Quoted<T> {
  value: T
  quote: string
}

export interface IncidentCandidate {
  report: string
  language: string
  incident_type: Quoted<import('../types').IncidentType> | null
  location_text: Quoted<string> | null
  people_count: Quoted<number> | null
  needs: { resource_type: import('../types').ResourceType; quantity: number; quote: string }[]
  signals: { signal: Signal; quote: string }[]
  severity: import('../types').Severity
  severity_rule: string
  geocode: { lat: number; lon: number; name: string; osm: string; kind: string; method: string; score: number } | null
  dropped: string[]
}

export interface ConfirmedFields {
  incident_type: import('../types').IncidentType
  place: { name: string; lat: number; lon: number }
  people_count: number | null
  needs: Partial<Record<import('../types').ResourceType, number>>
  signals: Signal[]
}

export interface IntakeReport {
  id: number
  received_at: string
  text: string
  source: string
  status: 'unread' | 'needs_review' | 'ready' | 'confirmed' | 'merged' | 'dismissed'
  candidate: IncidentCandidate | null
  read_meta: { model: string; prompt_version: string; input_tokens?: number; output_tokens?: number; latency_s?: number; cost_usd?: number } | null
  review_reasons: string[]
  suggested_fields: ConfirmedFields | null
  confirmed_fields: ConfirmedFields | null
  edited_fields: string[] | null
  reviewed_by: string | null
  merged_into: number | null
  incident_id: string | null
  exercise_id: string | null
  duplicates: { id: number; rule: string; text_score: number }[]
}

export interface PlaceMatch {
  name: string
  kind: 'place' | 'landmark' | 'road'
  lat: number
  lon: number
  osm: string
}
