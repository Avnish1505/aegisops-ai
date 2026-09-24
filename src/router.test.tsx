import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider, createMemoryHistory } from '@tanstack/react-router'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { createAppRouter } from './router'

function renderAt(path: string) {
  const queryClient = new QueryClient()
  const router = createAppRouter(queryClient, createMemoryHistory({ initialEntries: [path] }))
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

describe('routes', () => {
  it.each([
    ['/triage', 'Intake triage'],
    ['/plans/7', 'Plan review'],
    ['/audit/7', 'Audit'],
    ['/evals', 'Evals'],
  ])('%s renders %s under the status bar', async (path, title) => {
    renderAt(path)
    expect(await screen.findByRole('heading', { name: title })).toBeTruthy()
    expect(screen.getByText('EXERCISE')).toBeTruthy()
    expect(screen.getByLabelText('Clock, India Standard Time').textContent).toMatch(/IST$/)
  })

  it('unknown paths show not found', async () => {
    renderAt('/nowhere')
    expect(await screen.findByRole('heading', { name: 'Not found' })).toBeTruthy()
  })
})
