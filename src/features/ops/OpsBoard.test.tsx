import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider, createMemoryHistory } from '@tanstack/react-router'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createAppRouter } from '../../router'
import { TOKEN, fakeApi } from '../../test/fakeApi'
import type { Scenario } from '../../types'

const scenario: Scenario = {
  scenario_id: 'EX-1', sim_start_min: 0,
  incidents: [
    { id: 'INC-2', type: 'medical', severity: 'high', location: { lat: 26.85, lon: 80.94 }, people_affected: 2, reported_at_min: 50, resources_needed: { ambulance: 1 }, report: 'Hazratganj: fall' },
    { id: 'INC-1', type: 'flood', severity: 'critical', location: { lat: 26.83, lon: 80.92 }, people_affected: 35, reported_at_min: 20, resources_needed: { boat: 1 }, report: 'Charbagh: rooftops' },
  ],
  resources: [{ id: 'RES-BOAT-1', type: 'boat', location: { lat: 26.84, lon: 80.93 }, available: true, speed_kmh: 20 }],
}

function renderBoard() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createAppRouter(queryClient, createMemoryHistory({ initialEntries: ['/'] }))
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return router
}

afterEach(() => vi.unstubAllGlobals())

describe('operations board', () => {
  it('lists incidents by priority, place first, with age and plan state; J/K select; Enter opens the plan', async () => {
    const seeded = new Date(Date.now()).toISOString()
    fakeApi({
      'POST /api/v1/dev/token': TOKEN,
      'GET /api/v1/status': {
        server_time: seeded, pending_approvals: 1,
        feeds: [{ source: 'sachet', state: 'failing', last_ok_at: null, last_poll_at: seeded, last_error: 'HTTP 503', interval_min: 5 }],
        model: { configured: false, model: 'm', provider: 'nvidia' },
        exercise: { id: 'EX-1', name: 'Test exercise', started_at: seeded },
      },
      'GET /api/v1/exercises/EX-1': scenario,
      'GET /api/v1/decisions': [{ decision_id: 9 }],
      'GET /api/v1/decisions/9': {
        decision_id: 9, scenario_id: 'EX-1', status: 'requires_human_approval', scenario,
        assignments: [], unmet_requirements: [{ incident_id: 'INC-1', resource_type: 'boat', quantity: 1, severity: 'critical' }],
        travel_times: { provider: 'osrm-driving', degraded: false, degraded_reason: null, minutes: { 'RES-BOAT-1': { 'INC-1': 4.2, 'INC-2': 3 } } },
      },
      'POST /api/v1/labels': { incidents: { 'INC-1': 'Charbagh', 'INC-2': 'Hazratganj' }, units: { 'RES-BOAT-1': 'Police Station' } },
      'GET /api/v1/events': [],
    })
    const router = renderBoard()

    const queue = await screen.findByRole('listbox', { name: /Incidents/ })
    const rows = await within(queue).findAllByRole('option')
    await waitFor(() =>
      expect(rows.map((row) => row.textContent)).toEqual([
        expect.stringMatching(/^Critical\s*Charbagh\s*30 min\s*INC-1.*Short: 1 boat/),
        expect.stringMatching(/^High\s*Hazratganj\s*0 min\s*INC-2.*assigned/),
      ]),
    )
    expect(screen.getByText('failing').parentElement?.className).toMatch(/text-high/)

    await userEvent.keyboard('j')
    expect(rows[0].getAttribute('aria-selected')).toBe('true')
    expect(screen.getByRole('heading', { level: 3, name: 'Charbagh' })).toBeTruthy()
    expect(screen.getByText('4.2 min')).toBeTruthy()

    await userEvent.keyboard('{Enter}')
    expect(router.state.location.pathname).toBe('/plans/9')
  })
})
