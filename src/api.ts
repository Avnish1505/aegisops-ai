import type { Decision, Scenario } from './types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
const DEVELOPMENT_ROLE = import.meta.env.VITE_DEVELOPMENT_ROLE ?? 'operator'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, init)
  } catch {
    throw new Error(`Could not reach AegisOps API at ${API_BASE_URL}. Confirm the backend is running on port 8000.`)
  }

  if (!response.ok) {
    let detail = `Request failed (${response.status}).`
    try {
      const payload = (await response.json()) as { detail?: string }
      if (payload.detail) detail = payload.detail
    } catch {
      // The server returned a non-JSON error; the status above is still useful to an operator.
    }
    throw new Error(detail)
  }

  return response.json() as Promise<T>
}

export function fetchScenario(seed?: number): Promise<Scenario> {
  const query = seed === undefined ? '' : `?seed=${encodeURIComponent(seed)}`
  return request<Scenario>(`/api/v1/scenarios${query}`)
}

export function fetchDecision(scenario: Scenario): Promise<Decision> {
  return request<Decision>('/api/v1/decisions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer role:${DEVELOPMENT_ROLE}`,
    },
    body: JSON.stringify({ scenario }),
  })
}
