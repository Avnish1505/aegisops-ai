import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { StoredDecision } from '../../api/types'
import { AssignmentsTable } from './AssignmentsTable'
import { DraftText } from './SitrepDraft'

describe('SITREP number mismatches', () => {
  it('marks the wrong number on its line and explains it to screen readers', () => {
    render(
      <DraftText
        text={'SITREP X\nINC-1 critical flood: RES-A boat ETA 5.0 min.'}
        problems={[{ line: 2, written: '5.0', message: 'line 2: RES-A ETA for INC-1 is 9.4, draft says 5.0' }]}
      />,
    )
    const mark = screen.getByText('5.0')
    expect(mark.tagName).toBe('MARK')
    expect(screen.getByText(/Number does not match the plan: line 2/)).toBeTruthy()
    expect(screen.getByText('SITREP X').tagName).toBe('DIV')
  })
})

describe('assignments', () => {
  it('shows the verified ETA and, when the plan claimed another, the claim in red', () => {
    const plan = {
      assignments: [{ incident_id: 'INC-1', resource_id: 'RES-A', resource_type: 'boat', travel_minutes: 5, citations: [] }],
      unmet_requirements: [],
      scenario: {
        scenario_id: 'S', sim_start_min: 0,
        incidents: [{ id: 'INC-1', type: 'flood', severity: 'critical', location: { lat: 0, lon: 0 }, people_affected: 1, reported_at_min: 0, resources_needed: { boat: 1 } }],
        resources: [{ id: 'RES-A', type: 'boat', location: { lat: 0, lon: 0 }, available: true, speed_kmh: 20 }],
      },
      travel_times: { provider: 'osrm-driving', degraded: false, degraded_reason: null, minutes: { 'RES-A': { 'INC-1': 9.4 } } },
      verification: {
        verdict: 'blocked', blocking_check_ids: ['travel_time_matches'], safety_gate_blocked: false,
        checks: [{ id: 'travel_time_matches', passed: false, severity: 'critical', message: 'Travel times differ from osrm-driving beyond tolerance: RES-A', offending_ids: ['RES-A'] }],
      },
    } as unknown as StoredDecision
    render(<AssignmentsTable plan={plan} labels={{ incidents: { 'INC-1': 'Charbagh' }, units: { 'RES-A': 'Police Station' } }} />)
    expect(screen.getByText('9.4 min')).toBeTruthy()
    expect(screen.getByText('plan claims 5.0 min').className).toMatch(/text-critical/)
    expect(screen.getByText('Charbagh')).toBeTruthy()
  })
})
