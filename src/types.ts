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

export interface Assignment {
  incident_id: string
  resource_id: string
  resource_type: ResourceType
  travel_minutes: number
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
  advisory_confidence: number
  decision_trace: string[]
}
