import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider, createMemoryHistory } from '@tanstack/react-router'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { IntakeReport } from '../../api/types'
import { IDENTITIES, signIn } from '../../lib/auth'
import { createAppRouter } from '../../router'
import { TOKEN, fakeApi } from '../../test/fakeApi'

const TEXT = 'Charbagh station ke peeche kamar tak pani, lagbhag 35 log chhat par fanse hain.'
const report: IntakeReport = {
  id: 4, received_at: new Date().toISOString(), text: TEXT, source: 'operator', status: 'needs_review',
  candidate: {
    report: TEXT, language: 'hinglish',
    incident_type: { value: 'flood', quote: 'kamar tak pani' },
    location_text: { value: 'Charbagh station', quote: 'Charbagh station ke peeche' },
    people_count: null, needs: [], signals: [{ signal: 'trapped', quote: 'chhat par fanse hain' }],
    severity: 'high', severity_rule: 'R4 trapped', dropped: ['people_count'],
    geocode: { lat: 26.83, lon: 80.92, name: 'Charbagh', osm: 'node/1', kind: 'place', method: 'exact', score: 100 },
  },
  read_meta: { model: 'nvidia/llama-3.1-nemotron-70b-instruct', prompt_version: 'reader-v1' },
  review_reasons: ['field_dropped:people_count'],
  suggested_fields: { incident_type: 'flood', place: { name: 'Charbagh', lat: 26.83, lon: 80.92 }, people_count: null, needs: {}, signals: ['trapped'] },
  confirmed_fields: null, edited_fields: null, reviewed_by: null, merged_into: null, incident_id: null, exercise_id: null,
  duplicates: [{ id: 3, rule: 'near-identical text', text_score: 96 }],
}

beforeEach(() => signIn(IDENTITIES.dev[0]))
afterEach(() => vi.unstubAllGlobals())

describe('intake triage', () => {
  it('shows quotes and why the report needs review, previews rule severity, and confirms edited fields', async () => {
    const api = fakeApi({
      'POST /api/v1/dev/token': TOKEN,
      'GET /api/v1/status': { feeds: [], model: { configured: false, model: 'm', provider: 'nvidia' }, pending_approvals: 0, exercise: null, server_time: '' },
      'GET /api/v1/intake': [report],
      'POST /api/v1/intake/severity-preview': (init?: RequestInit) =>
        JSON.parse(String(init?.body)).fields.people_count >= 50
          ? { severity: 'critical', rule: 'R3 50 or more people' }
          : { severity: 'high', rule: 'R4 trapped' },
      'POST /api/v1/intake/4/confirm': { ...report, status: 'confirmed', incident_id: 'INC-TRI-4', edited_fields: ['people_count'] },
      'GET /api/v1/events': [],
    })
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const router = createAppRouter(client, createMemoryHistory({ initialEntries: ['/triage?report=4'] }))
    render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>)

    expect(await screen.findAllByText(/Dropped people count: its quote is not in the report/)).toHaveLength(2)
    const place = screen.getByTitle('place')
    expect(place.tagName).toBe('MARK')
    expect(place.textContent).toContain('Charbagh station ke peeche')
    expect(await screen.findByText('R4 trapped')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Merge into #3' })).toBeTruthy()

    await userEvent.type(screen.getByLabelText('People affected'), '60')
    expect(await screen.findByText('R3 50 or more people')).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: 'Confirm and add to exercise' }))

    await waitFor(() => expect(api.calls).toContain('POST /api/v1/intake/4/confirm'))
    const body = api.fetchMock.mock.calls.find(([url]) => String(url).endsWith('/confirm'))?.[1]?.body
    expect(JSON.parse(String(body)).fields).toMatchObject({ incident_type: 'flood', people_count: 60, signals: ['trapped'] })
    expect(await screen.findByText(/Added to the exercise as/)).toBeTruthy()
  })
})
