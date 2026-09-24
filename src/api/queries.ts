import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/http'
import type { PlanningConstraint, Scenario } from '../types'
import type { ConstraintProposal, ReportDrafts } from '../types'
import type {
  AlertSummary,
  AuditEvent,
  Baseline,
  DecisionSummary,
  DispositionResult,
  Labels,
  ReasonCodes,
  Reverification,
  RouteGeometry,
  StatusResponse,
  StoredDecision,
} from './types'

export const keys = {
  status: ['status'] as const,
  exercise: (id: string) => ['exercise', id] as const,
  decisions: (filter: Record<string, string | number | boolean | undefined>) =>
    ['decisions', filter] as const,
  decision: (id: number) => ['decision', id] as const,
  events: (decisionId?: number) => ['events', decisionId ?? 'all'] as const,
  labels: (scenarioId: string) => ['labels', scenarioId] as const,
  routes: (decisionId: number) => ['routes', decisionId] as const,
  alerts: ['alerts'] as const,
}

function query(params: Record<string, string | number | boolean | undefined>): string {
  const entries = Object.entries(params).filter(([, value]) => value !== undefined && value !== '')
  return entries.length ? `?${new URLSearchParams(entries.map(([k, v]) => [k, String(v)]))}` : ''
}

export const statusQuery = queryOptions({
  queryKey: keys.status,
  queryFn: () => api<StatusResponse>('/api/v1/status'),
  refetchInterval: 60_000, // ages tick in the UI; this only refreshes feed state if SSE drops
})

export function useStatus() {
  return useQuery(statusQuery)
}

export function useExercise(id: string | undefined) {
  return useQuery({
    queryKey: keys.exercise(id ?? ''),
    queryFn: () => api<Scenario>(`/api/v1/exercises/${encodeURIComponent(id ?? '')}`, { auth: false }),
    enabled: Boolean(id),
    staleTime: Infinity,
  })
}

export function useDecisions(filter: { scenario_id?: string; status?: string; pending?: boolean; limit?: number }) {
  return useQuery({
    queryKey: keys.decisions(filter),
    queryFn: () => api<DecisionSummary[]>(`/api/v1/decisions${query(filter)}`),
  })
}

export function useDecision(id: number | undefined) {
  return useQuery({
    queryKey: keys.decision(id ?? 0),
    queryFn: () => api<StoredDecision>(`/api/v1/decisions/${id}`),
    enabled: id !== undefined && Number.isFinite(id),
  })
}

export function useEvents(decisionId?: number, limit = 40) {
  return useQuery({
    queryKey: keys.events(decisionId),
    queryFn: () => api<AuditEvent[]>(`/api/v1/events${query({ decision_id: decisionId, limit })}`),
  })
}

export function useLabels(scenario: Scenario | undefined) {
  return useQuery({
    queryKey: keys.labels(scenario?.scenario_id ?? ''),
    queryFn: () => api<Labels>('/api/v1/labels', { method: 'POST', body: scenario }),
    enabled: Boolean(scenario),
    staleTime: Infinity,
  })
}

export function usePlan() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: {
      scenario: Scenario
      constraints?: PlanningConstraint[]
      constraintSources?: ({ note: string; quote: string | null } | null)[]
      traceparent?: string
    }) =>
      api<StoredDecision>('/api/v1/decisions', {
        method: 'POST',
        body: {
          scenario: input.scenario,
          constraints: input.constraints ?? [],
          constraint_sources: input.constraintSources ?? [],
        },
        headers: input.traceparent ? { traceparent: input.traceparent } : undefined,
      }),
    onSuccess: (decision) => {
      client.setQueryData(keys.decision(decision.decision_id), decision)
      void client.invalidateQueries({ queryKey: ['decisions'] })
      void client.invalidateQueries({ queryKey: keys.status })
    },
  })
}

export function useRoutes(decisionId: number | undefined) {
  return useQuery({
    queryKey: keys.routes(decisionId ?? 0),
    queryFn: () => api<RouteGeometry[]>(`/api/v1/decisions/${decisionId}/routes`),
    enabled: decisionId !== undefined,
    staleTime: Infinity, // a stored plan's routes never change
  })
}

export function useAlerts() {
  return useQuery({
    queryKey: keys.alerts,
    queryFn: () => api<AlertSummary[]>('/api/v1/alerts?source=sachet&limit=100', { auth: false }),
  })
}

export function useBaseline(decisionId: number | undefined) {
  return useQuery({
    queryKey: ['baseline', decisionId],
    queryFn: () => api<Baseline>(`/api/v1/decisions/${decisionId}/baseline`),
    enabled: decisionId !== undefined,
    staleTime: Infinity,
  })
}

export function useReasonCodes() {
  return useQuery({
    queryKey: ['reason-codes'],
    queryFn: () => api<ReasonCodes>('/api/v1/reason-codes', { auth: false }),
    staleTime: Infinity,
  })
}

export function useDisposition(decisionId: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: { action: 'approve' | 'reject'; reason_code: string; reason?: string }) =>
      api<DispositionResult>(`/api/v1/decisions/${decisionId}/disposition`, { method: 'POST', body: input }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.decision(decisionId) })
      void client.invalidateQueries({ queryKey: ['decisions'] })
      void client.invalidateQueries({ queryKey: keys.status })
      void client.invalidateQueries({ queryKey: ['events'] })
    },
  })
}

export function useDrafts(decisionId: number) {
  return useMutation({
    mutationFn: () => api<ReportDrafts>(`/api/v1/decisions/${decisionId}/drafts`, { method: 'POST' }),
  })
}

export function useTranslate() {
  return useMutation({
    mutationFn: (input: { note: string; scenario: Scenario }) =>
      api<ConstraintProposal>('/api/v1/constraints/translate', { method: 'POST', body: input }),
  })
}

export function useReverify(decisionId: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => api<Reverification>(`/api/v1/decisions/${decisionId}/reverify`, { method: 'POST' }),
    onSuccess: () => void client.invalidateQueries({ queryKey: ['events'] }),
  })
}
