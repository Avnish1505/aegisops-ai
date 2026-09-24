import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider, createMemoryHistory } from '@tanstack/react-router'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { IDENTITIES, signIn } from '../../lib/auth'
import { createAppRouter } from '../../router'
import { TOKEN, fakeApi } from '../../test/fakeApi'

const session = {
  id: 4, participant: 'P02', participant_number: 2,
  tasks: [
    { id: 40, order: 1, ui: 'console', task: 'B1', decision_id: 70, started: true, decided: true },
    { id: 41, order: 2, ui: 'console', task: 'B2', decision_id: 71, started: false, decided: false },
  ],
}

afterEach(() => vi.unstubAllGlobals())

function renderRunner() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createAppRouter(client, createMemoryHistory({ initialEntries: ['/study/4'] }))
  render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>)
  return router
}

describe('study runner', () => {
  it('asks for an approver identity before a task can start', async () => {
    signIn(IDENTITIES.dev[0]) // operator
    fakeApi({ 'POST /api/v1/dev/token': TOKEN, 'GET /api/v1/study/sessions/4': session })
    renderRunner()
    expect(await screen.findByText(/Sign in as an approver/)).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Open plan 2' }).hasAttribute('disabled')).toBe(true)
  })

  it('starts the clock, then opens the next undecided plan in the assigned interface', async () => {
    signIn(IDENTITIES.dev[1]) // alice, approver
    const api = fakeApi({
      'POST /api/v1/dev/token': TOKEN,
      'GET /api/v1/study/sessions/4': session,
      'POST /api/v1/study/tasks/41/start': { id: 41, started_at: 't' },
      'GET /api/v1/decisions/71': new Response(JSON.stringify({ detail: 'x' }), { status: 404 }),
    })
    const router = renderRunner()
    expect(await screen.findByText(/1 of 12 plans decided/)).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: 'Open plan 2' }))
    expect(api.calls).toContain('POST /api/v1/study/tasks/41/start')
    expect(router.state.location.pathname).toBe('/plans/71')
    expect(router.state.location.search).toEqual({ study: 4 })
  })
})
