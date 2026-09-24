import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider, createMemoryHistory } from '@tanstack/react-router'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { IDENTITIES, signIn } from '../../lib/auth'
import { createAppRouter } from '../../router'
import { TOKEN, fakeApi } from '../../test/fakeApi'

beforeEach(() => {
  signIn(IDENTITIES.dev[0])
  fakeApi({
    'POST /api/v1/dev/token': TOKEN,
    'GET /api/v1/status': { feeds: [], model: { configured: false, model: 'm', provider: 'nvidia' }, pending_approvals: 0, exercise: null, server_time: '' },
    'GET /api/v1/reports': { fault_injection: null, eval: null, llm_vs_solver: null, user_study: null, superseded: [] },
    'GET /api/v1/decisions': [{ decision_id: 12, status: 'blocked', disposition: null }],
    'GET /api/v1/intake': [],
  })
})
afterEach(() => vi.unstubAllGlobals())

function renderApp() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createAppRouter(client, createMemoryHistory({ initialEntries: ['/evals'] }))
  render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>)
  return router
}

describe('command palette and shortcuts', () => {
  it('Cmd+K opens the palette; choosing an item navigates', async () => {
    const router = renderApp()
    await screen.findByRole('heading', { name: 'Evaluations' })
    await userEvent.keyboard('{Meta>}k{/Meta}')
    await userEvent.type(await screen.findByPlaceholderText(/Go to/), 'triage')
    await userEvent.keyboard('{Enter}')
    await waitFor(() => expect(router.state.location.pathname).toBe('/triage'))
  })

  it('lists recent plans, blocked ones marked', async () => {
    renderApp()
    await screen.findByRole('heading', { name: 'Evaluations' })
    await userEvent.keyboard('{Control>}k{/Control}')
    expect(await screen.findByText('BLOCKED')).toBeTruthy()
  })

  it('? opens the shortcut sheet', async () => {
    renderApp()
    await screen.findByRole('heading', { name: 'Evaluations' })
    await userEvent.keyboard('?')
    expect(await screen.findByRole('heading', { name: 'Keyboard shortcuts' })).toBeTruthy()
    expect(screen.getByText(/Approve \(plan review/)).toBeTruthy()
  })
})
