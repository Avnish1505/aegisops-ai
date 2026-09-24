import type { TravelTimeMatrix } from '../api/types'
import type { Assignment, Decision, Incident, Resource, ResourceType, Scenario, Severity, UnmetRequirement } from '../types'

export const SEVERITY_RANK: Record<Severity, number> = { critical: 3, high: 2, medium: 1, low: 0 }

export interface IncidentState {
  kind: 'unplanned' | 'covered' | 'short'
  assigned: Assignment[]
  unmet: UnmetRequirement[]
}

export function incidentState(incident: Incident, plan: Pick<Decision, 'assignments' | 'unmet_requirements'> | undefined): IncidentState {
  if (!plan) return { kind: 'unplanned', assigned: [], unmet: [] }
  const assigned = plan.assignments.filter((a) => a.incident_id === incident.id)
  const unmet = plan.unmet_requirements.filter((u) => u.incident_id === incident.id)
  return { kind: unmet.length ? 'short' : 'covered', assigned, unmet }
}

/**
 * Wall-clock time an incident was reported. An exercise is seeded at the moment its last report
 * arrives: that report is ``seededAtMs``, and every other one is earlier by the difference in
 * ``reported_at_min``.
 */
export function reportedAtMs(incident: Incident, seededAtMs: number, latestReportMin: number): number {
  return seededAtMs - (latestReportMin - incident.reported_at_min) * 60_000
}

export function latestReportMin(incidents: Incident[]): number {
  return incidents.reduce((latest, incident) => Math.max(latest, incident.reported_at_min), 0)
}

/** Queue order: severity, then any shortfall in the current plan, then oldest first, then id. */
export function byPriority(
  incidents: Incident[],
  plan: Pick<Decision, 'assignments' | 'unmet_requirements'> | undefined,
): Incident[] {
  return [...incidents].sort((a, b) => {
    const severity = SEVERITY_RANK[b.severity] - SEVERITY_RANK[a.severity]
    if (severity) return severity
    const short = Number(incidentState(b, plan).kind === 'short') - Number(incidentState(a, plan).kind === 'short')
    if (short) return short
    const age = a.reported_at_min - b.reported_at_min
    return age || a.id.localeCompare(b.id)
  })
}

export interface UnitOption {
  unit: Resource
  minutes: number
}

/** Up to ``limit`` available units per needed type, fastest first, from the plan's own matrix. */
export function nearestCapableUnits(
  incident: Incident,
  scenario: Scenario,
  matrix: TravelTimeMatrix | undefined,
  limit = 3,
): Partial<Record<ResourceType, UnitOption[]>> {
  const result: Partial<Record<ResourceType, UnitOption[]>> = {}
  if (!matrix) return result
  for (const type of Object.keys(incident.resources_needed) as ResourceType[]) {
    result[type] = scenario.resources
      .filter((unit) => unit.type === type && unit.available)
      .map((unit) => ({ unit, minutes: matrix.minutes[unit.id]?.[incident.id] }))
      .filter((option): option is UnitOption => typeof option.minutes === 'number')
      .sort((a, b) => a.minutes - b.minutes || a.unit.id.localeCompare(b.unit.id))
      .slice(0, limit)
  }
  return result
}

export const RESOURCE_LABEL: Record<ResourceType, string> = {
  ambulance: 'ambulance',
  fire_unit: 'fire unit',
  rescue_team: 'rescue team',
  hazmat_unit: 'hazmat unit',
  boat: 'boat',
}

export const INCIDENT_LABEL: Record<Incident['type'], string> = {
  flood: 'Flood',
  medical: 'Medical',
  fire: 'Fire',
  structural_collapse: 'Structural collapse',
  hazmat: 'Hazmat',
}

export function minutes(value: number): string {
  return `${value.toFixed(1)} min`
}
