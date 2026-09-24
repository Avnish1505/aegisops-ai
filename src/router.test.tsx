import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider, createMemoryHistory } from '@tanstack/react-router'
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createAppRouter } from './router'
import { TOKEN, fakeApi } from './test/fakeApi'

function renderAt(path: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createAppRouter(queryClient, createMemoryHistory({ initialEntries: [path] }))
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

afterEach(() => vi.unstubAllGlobals())

describe('routes', () => {
  it('evals renders under the status bar with the IST clock', async () => {
    fakeApi({
      'POST /api/v1/dev/token': TOKEN,
      'GET /api/v1/status': { feeds: [], model: { configured: false, model: 'm', provider: 'nvidia' }, pending_approvals: 0, exercise: null, server_time: '' },
      'GET /api/v1/reports': { fault_injection: null, eval: null, llm_vs_solver: null, user_study: null, superseded: [] },
    })
    renderAt('/evals')
    expect(await screen.findByRole('heading', { name: 'Evaluations' })).toBeTruthy()
    expect(screen.getAllByText('Not run yet.')).toHaveLength(4)
    expect(screen.getByText('EXERCISE')).toBeTruthy()
    expect(screen.getByLabelText('Clock, India Standard Time').textContent).toMatch(/IST$/)
  })

  it('unknown paths show not found', async () => {
    fakeApi({ 'POST /api/v1/dev/token': TOKEN })
    renderAt('/nowhere')
    expect(await screen.findByRole('heading', { name: 'Not found' })).toBeTruthy()
  })
})
