import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider, createMemoryHistory } from '@tanstack/react-router'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { IDENTITIES, signIn } from '../../lib/auth'
import { createAppRouter } from '../../router'
import { TOKEN, fakeApi } from '../../test/fakeApi'

beforeEach(() => signIn(IDENTITIES.dev[0]))
afterEach(() => vi.unstubAllGlobals())

describe('audit', () => {
  it('shows a broken chain link and a re-verification that differs from the stored report', async () => {
    fakeApi({
      'POST /api/v1/dev/token': TOKEN,
      'GET /api/v1/status': { feeds: [], model: { configured: false, model: 'm', provider: 'nvidia' }, pending_approvals: 0, exercise: null, server_time: '' },
      'GET /api/v1/decisions/5': { decision_id: 5, scenario_sha256: 'abc123' },
      'GET /api/v1/events': [
        { id: 2, ts: '2026-09-24T06:00:01Z', actor: 'verifier', type: 'verification_completed', payload: { decision_id: 5, verdict: 'pass', failed_check_ids: [] }, prev_hash: 'h1', hash: 'h2' },
        { id: 1, ts: '2026-09-24T06:00:00Z', actor: 'olive', type: 'decision_created', payload: { decision_id: 5, engine: 'cp_sat_v1', status: 'requires_human_approval', scenario_sha256: 'abc123' }, prev_hash: '0', hash: 'h1' },
      ],
      'GET /api/v1/audit/verify': { ok: false, events_checked: 2, head_hash: 'h2', first_broken: { event_id: 2, reason: 'hash does not match its contents' } },
      'POST /api/v1/decisions/5/reverify': {
        decision_id: 5, matches: false, same_verdict: false, differing_checks: ['travel_time_matches'],
        stored: { verdict: 'pass', checks: [] }, recomputed: { verdict: 'blocked', checks: [] },
        scenario_sha256: 'abc123', scenario_sha256_matches: true, event_id: 3,
      },
    })
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const router = createAppRouter(client, createMemoryHistory({ initialEntries: ['/audit/5'] }))
    render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>)

    const broken = await screen.findByText(/Broken at event/)
    expect(broken.textContent).toContain('#2')
    const titles = screen.getAllByText(/Plan proposed|Plan verified/).map((node) => node.textContent)
    expect(titles).toEqual(['Plan proposed', 'Plan verified']) // oldest first

    await userEvent.click(screen.getByRole('button', { name: 'Re-verify stored inputs' }))
    const differs = await screen.findByText(/Differs from the stored report/)
    expect(differs.textContent).toContain('travel_time_matches')
  })
})
