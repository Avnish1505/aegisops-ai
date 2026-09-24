import { describe, expect, it } from 'vitest'
import type { Incident, Scenario } from '../types'
import { byPriority, incidentState, latestReportMin, nearestCapableUnits, reportedAtMs } from './incidents'

const incident = (id: string, severity: Incident['severity'], reported: number): Incident => ({
  id, type: 'flood', severity, location: { lat: 26.8, lon: 80.9 }, people_affected: 1,
  reported_at_min: reported, resources_needed: { boat: 1 },
})

describe('incident priority', () => {
  const incidents = [incident('B', 'high', 5), incident('A', 'critical', 30), incident('C', 'high', 1), incident('D', 'high', 9)]
  const plan = {
    assignments: [],
    unmet_requirements: [{ incident_id: 'D', resource_type: 'boat' as const, quantity: 1, severity: 'high' as const }],
  }

  it('orders by severity, then shortfall, then oldest first', () => {
    expect(byPriority(incidents, plan).map((i) => i.id)).toEqual(['A', 'D', 'C', 'B'])
  })

  it('without a plan nothing is short and nothing is covered', () => {
    expect(incidentState(incidents[0], undefined).kind).toBe('unplanned')
    expect(incidentState(incidents[3], plan).kind).toBe('short')
    expect(incidentState(incidents[1], plan).kind).toBe('covered')
  })
})

describe('nearest capable units', () => {
  const scenario: Scenario = {
    scenario_id: 'S', sim_start_min: 0, incidents: [incident('I', 'high', 0)],
    resources: [
      { id: 'BOAT-far', type: 'boat', location: { lat: 0, lon: 0 }, available: true, speed_kmh: 20 },
      { id: 'BOAT-near', type: 'boat', location: { lat: 0, lon: 0 }, available: true, speed_kmh: 20 },
      { id: 'BOAT-busy', type: 'boat', location: { lat: 0, lon: 0 }, available: false, speed_kmh: 20 },
      { id: 'AMB-1', type: 'ambulance', location: { lat: 0, lon: 0 }, available: true, speed_kmh: 30 },
    ],
  }
  const matrix = {
    provider: 'osrm-driving', degraded: false, degraded_reason: null,
    minutes: { 'BOAT-far': { I: 12 }, 'BOAT-near': { I: 4.2 }, 'BOAT-busy': { I: 1 }, 'AMB-1': { I: 2 } },
  }

  it('lists only available units of a needed type, fastest first', () => {
    const options = nearestCapableUnits(scenario.incidents[0], scenario, matrix)
    expect(Object.keys(options)).toEqual(['boat'])
    expect(options.boat?.map((o) => [o.unit.id, o.minutes])).toEqual([['BOAT-near', 4.2], ['BOAT-far', 12]])
  })
})

describe('exercise clock', () => {
  it('treats the seed time as the moment the last report arrived', () => {
    const incidents = [incident('A', 'low', 60), incident('B', 'low', 15)]
    const seeded = Date.UTC(2026, 8, 24, 6, 0)
    const latest = latestReportMin(incidents)
    expect(reportedAtMs(incidents[0], seeded, latest)).toBe(seeded)
    expect(reportedAtMs(incidents[1], seeded, latest)).toBe(seeded - 45 * 60_000)
  })
})
