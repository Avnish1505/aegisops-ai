export type Severity = 'low' | 'medium' | 'high' | 'critical'
export type IncidentType = 'medical' | 'fire' | 'structural_collapse' | 'flood' | 'hazmat'
export type ResourceType = 'ambulance' | 'fire_unit' | 'rescue_team' | 'hazmat_unit'

export interface Incident {
  id: string
  type: IncidentType
  severity: Severity
  location: [number, number]
  people_affected: number
  reported_at_min: number
  resources_needed: Partial<Record<ResourceType, number>>
}

export interface Resource {
  id: string
  type: ResourceType
  location: [number, number]
  available: boolean
  eta_speed: number
}

export interface Scenario {
  scenario_id: string
  incidents: Incident[]
  resources: Resource[]
  sim_start_min: number
}

export interface Citation {
  evidence_id: string
  quote: string
}

export interface Assignment {
  incident_id: string
  resource_id: string
  resource_type: ResourceType
  travel_minutes: number
  citations: Citation[]
}

export interface UnmetRequirement {
  incident_id: string
  resource_type: ResourceType
  quantity: number
  severity: Severity
}

export interface SafetyFinding {
  code: string
  severity: 'warning' | 'critical' | string
  message: string
  incident_id: string | null
}

export interface Decision {
  scenario_id: string
  engine: string
  status: 'requires_human_approval' | 'blocked'
  requires_human_approval: boolean
  assignments: Assignment[]
  unmet_requirements: UnmetRequirement[]
  safety_findings: SafetyFinding[]
  coverage: number
  decision_trace: string[]
  // Set by POST /api/v1/decisions on every response — required to record a disposition.
  decision_id: number
  verification: VerificationReport
  drafts: TextDraft[]
  objective: number | null
  reference_objective: number | null
  solve_status: string | null
  travel_provider: string | null
  travel_degraded: boolean | null
}

export type CheckSeverity = 'critical' | 'high' | 'warning'

export interface CheckResult {
  id: string
  passed: boolean
  severity: CheckSeverity
  message: string
  offending_ids: string[]
}

export interface VerificationReport {
  verdict: 'pass' | 'blocked'
  checks: CheckResult[]
  blocking_check_ids: string[]
  safety_gate_blocked: boolean
}

export interface TextDraft {
  id: string
  kind: 'sitrep'
  text: string
}

export type SelectedEntity =
  | { kind: 'incident'; entity: Incident }
  | { kind: 'resource'; entity: Resource }
  | null

export type DispositionAction = 'approve' | 'reject'

/** Persisted result of POST /api/v1/decisions/{id}/disposition. */
export interface DispositionResult {
  decision_id: number
  disposition_id: number
  action: DispositionAction
  timestamp: string
}
