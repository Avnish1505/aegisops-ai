import type { QueryClient } from '@tanstack/react-query'
import {
  type RouterHistory,
  createRootRouteWithContext,
  createRoute,
  createRouter,
} from '@tanstack/react-router'
import { lazy } from 'react'
import { Audit } from './features/audit/Audit'
import { Evals } from './features/evals/Evals'
import { OpsBoard } from './features/ops/OpsBoard'
import { PlanReview } from './features/plan/PlanReview'
import { Triage } from './features/triage/Triage'
import { NotFound, RootLayout } from './components/shell/RootLayout'

export interface RouterContext {
  queryClient: QueryClient
}

const OpsMap = lazy(() => import('./features/map/OpsMap'))

const decisionIdParams = {
  parse: (params: { decisionId: string }) => ({ decisionId: Number(params.decisionId) }),
  stringify: (params: { decisionId: number }) => ({ decisionId: String(params.decisionId) }),
}

const rootRoute = createRootRouteWithContext<RouterContext>()({
  component: RootLayout,
  notFoundComponent: NotFound,
})

const opsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  validateSearch: (search: Record<string, unknown>): { incident?: string } =>
    typeof search.incident === 'string' ? { incident: search.incident } : {},
  component: function OpsRoute() {
    const { incident } = opsRoute.useSearch()
    return <OpsBoard key={incident} initialIncident={incident} mapSlot={(props) => <OpsMap {...props} />} />
  },
})

const planRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/plans/$decisionId',
  params: decisionIdParams,
  component: function PlanRoute() {
    const { decisionId } = planRoute.useParams()
    return <PlanReview decisionId={decisionId} />
  },
})

const triageRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/triage',
  validateSearch: (search: Record<string, unknown>): { report?: number } =>
    typeof search.report === 'number' ? { report: search.report } : {},
  component: function TriageRoute() {
    const { report } = triageRoute.useSearch()
    return <Triage selected={report} />
  },
})

const auditRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/audit/$decisionId',
  params: decisionIdParams,
  component: function AuditRoute() {
    const { decisionId } = auditRoute.useParams()
    return <Audit decisionId={decisionId} />
  },
})

const evalsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/evals',
  component: Evals,
})

const routeTree = rootRoute.addChildren([opsRoute, planRoute, triageRoute, auditRoute, evalsRoute])

export function createAppRouter(queryClient: QueryClient, history?: RouterHistory) {
  return createRouter({ routeTree, history, context: { queryClient }, defaultPreload: 'intent' })
}

declare module '@tanstack/react-router' {
  interface Register {
    router: ReturnType<typeof createAppRouter>
  }
}
