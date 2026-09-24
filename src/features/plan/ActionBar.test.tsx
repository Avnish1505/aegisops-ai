import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { StoredDecision } from '../../api/types'
import { IDENTITIES, signIn } from '../../lib/auth'
import { TOKEN, fakeApi } from '../../test/fakeApi'
import { ActionBar } from './ActionBar'

const CODES = {
  approve: { reviewed_as_proposed: 'Reviewed; right as proposed' },
  reject: { eta_incorrect: 'An ETA is wrong', other: 'Other (explain)' },
}

function plan(overrides: Partial<StoredDecision> = {}): StoredDecision {
  return {
    decision_id: 7, scenario_id: 'S', engine: 'cp_sat_v1', status: 'requires_human_approval',
    requires_human_approval: true, assignments: [], unmet_requirements: [], safety_findings: [],
    coverage: 1, decision_trace: [], drafts: [], objective: 0, reference_objective: 0, solve_status: 'optimal',
    travel_provider: 'osrm-driving', travel_degraded: false, travel_degraded_reason: null,
    verification: { verdict: 'pass', checks: [], blocking_check_ids: [], safety_gate_blocked: false },
    scenario: { scenario_id: 'S', incidents: [], resources: [], sim_start_min: 0 }, scenario_sha256: 'x',
    proposer_sub: 'olive', created_at: '2026-09-24T06:00:00Z',
    travel_times: { provider: 'osrm-driving', minutes: {}, degraded: false, degraded_reason: null },
    constraints: [], constraint_sources: [], evidence: [], traceparent: null, approvals: [],
    ...overrides,
  }
}

const identity = (sub: string) => IDENTITIES.dev.find((i) => i.sub === sub) ?? null

function renderBar(decision: StoredDecision) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <ActionBar plan={decision} />
    </QueryClientProvider>,
  )
}

beforeEach(() => signIn(identity('olive')))
afterEach(() => vi.unstubAllGlobals())

describe('action bar', () => {
  it('gives Approve and Reject the same size and style', () => {
    signIn(identity('alice'))
    fakeApi({})
    renderBar(plan())
    const approve = screen.getByRole('button', { name: /Approve/ })
    const reject = screen.getByRole('button', { name: /Reject/ })
    expect(approve.className).toBe(reject.className)
  })

  it('tells the proposer they cannot approve their own plan', () => {
    signIn(identity('alice'))
    fakeApi({})
    renderBar(plan({ proposer_sub: 'alice' }))
    expect(screen.getByRole('button', { name: /Approve/ }).hasAttribute('disabled')).toBe(true)
    expect(screen.getByText(/Proposer cannot approve/)).toBeTruthy()
  })

  it('never lets a blocked plan be approved, and says which checks block it', () => {
    signIn(identity('alice'))
    fakeApi({})
    renderBar(plan({ status: 'blocked', verification: { verdict: 'blocked', checks: [], blocking_check_ids: ['travel_time_matches'], safety_gate_blocked: false } }))
    expect(screen.getByRole('button', { name: /Approve/ }).hasAttribute('disabled')).toBe(true)
    expect(screen.getByText(/Blocked plans cannot be approved/).textContent).toContain('travel_time_matches')
    expect(screen.getByRole('button', { name: /Reject/ }).hasAttribute('disabled')).toBe(false)
  })

  it('needs a reason code, and a note for "other", before rejecting', async () => {
    const api = fakeApi({
      'POST /api/v1/dev/token': TOKEN,
      'GET /api/v1/reason-codes': CODES,
      'POST /api/v1/decisions/7/disposition': (init?: RequestInit) => ({ decision_id: 7, disposition_id: 1, action: 'reject', reason_code: JSON.parse(String(init?.body)).reason_code, timestamp: 't' }),
    })
    renderBar(plan())
    await userEvent.keyboard('r')
    const submit = await screen.findByRole('button', { name: 'Record rejection' })
    expect(submit.hasAttribute('disabled')).toBe(true)
    await userEvent.click(await screen.findByLabelText(/Other/))
    expect(submit.hasAttribute('disabled')).toBe(true)
    await userEvent.type(screen.getByLabelText(/Note \(required\)/), 'Unit is at the workshop')
    await userEvent.click(submit)
    await waitFor(() => expect(api.calls).toContain('POST /api/v1/decisions/7/disposition'))
    const sent = api.fetchMock.mock.calls.find(([url]) => String(url).endsWith('/disposition'))?.[1]
    expect(JSON.parse(String(sent?.body))).toEqual({ action: 'reject', reason_code: 'other', reason: 'Unit is at the workshop' })
  })

  it('asks for confirmation before approving and shows a server refusal', async () => {
    signIn(identity('bob'))
    fakeApi({
      'POST /api/v1/dev/token': TOKEN,
      'GET /api/v1/reason-codes': CODES,
      'POST /api/v1/decisions/7/disposition': new Response(JSON.stringify({ detail: 'proposer cannot approve' }), { status: 409 }),
    })
    renderBar(plan())
    await userEvent.click(screen.getByRole('button', { name: /Approve/ }))
    await userEvent.click(await screen.findByLabelText(/Reviewed/))
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
    expect(screen.getByText(/Confirm approval of plan/)).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: 'Confirm approval' }))
    expect(await screen.findByText(/Refused by the server: proposer cannot approve/)).toBeTruthy()
  })
})
