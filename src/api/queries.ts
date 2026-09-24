import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/http'
import type { PlanningConstraint, Scenario } from '../types'
import type { AuditEvent, DecisionSummary, Labels, StatusResponse, StoredDecision } from './types'

export const keys = {
  status: ['status'] as const,
  exercise: (id: string) => ['exercise', id] as const,
  decisions: (filter: Record<string, string | number | boolean | undefined>) =>
    ['decisions', filter] as const,
  decision: (id: number) => ['decision', id] as const,
  events: (decisionId?: number) => ['events', decisionId ?? 'all'] as const,
  labels: (scenarioId: string) => ['labels', scenarioId] as const,
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
    mutationFn: (input: { scenario: Scenario; constraints?: PlanningConstraint[]; traceparent?: string }) =>
      api<StoredDecision>('/api/v1/decisions', {
        method: 'POST',
        body: { scenario: input.scenario, constraints: input.constraints ?? [] },
        headers: input.traceparent ? { traceparent: input.traceparent } : undefined,
      }),
    onSuccess: (decision) => {
      client.setQueryData(keys.decision(decision.decision_id), decision)
      void client.invalidateQueries({ queryKey: ['decisions'] })
      void client.invalidateQueries({ queryKey: keys.status })
    },
  })
}
