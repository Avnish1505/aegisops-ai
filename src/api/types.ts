import type { Assignment, Decision, Scenario } from '../types'

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
  constraints: unknown[]
  traceparent: string | null
  approvals: { disposition_id: number; action: 'approve' | 'reject'; actor: string; timestamp: string }[]
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
