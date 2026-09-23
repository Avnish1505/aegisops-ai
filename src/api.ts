import type { Decision, DispositionAction, DispositionResult, Scenario } from './types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

/** Development sign-in: tokens come from the API's /api/v1/dev/token, which exists only when the
 * API runs with AEGISOPS_ENVIRONMENT=development. Production needs a real OIDC login (not built). */
export const DEV_AUTH = import.meta.env.DEV || import.meta.env.VITE_DEV_AUTH === 'true'

export interface Identity {
  sub: string
  role: 'viewer' | 'operator' | 'approver' | 'admin'
  label: string
}

/** Two approvers, so the console can show that whoever proposes a plan cannot approve it,
 * and an operator, who can propose and reject but not approve. */
export const DEV_IDENTITIES: Identity[] = [
  { sub: 'alice', role: 'approver', label: 'Alice · approver' },
  { sub: 'bob', role: 'approver', label: 'Bob · approver' },
  { sub: 'olive', role: 'operator', label: 'Olive · operator' },
]

let currentIdentity: Identity = DEV_IDENTITIES[0]
const tokens = new Map<string, { token: string; expiresAt: number }>()

export function setIdentity(identity: Identity): void {
  currentIdentity = identity
}

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

async function authHeaders(): Promise<Record<string, string>> {
  if (!DEV_AUTH) return {}
  const { sub, role } = currentIdentity
  const cached = tokens.get(sub)
  if (cached && cached.expiresAt > Date.now()) return { Authorization: `Bearer ${cached.token}` }
  const issued = await request<{ access_token: string; expires_in: number }>('/api/v1/dev/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sub, role }),
  })
  // Refresh a minute early so a request never goes out with an expiring token.
  tokens.set(sub, { token: issued.access_token, expiresAt: Date.now() + (issued.expires_in - 60) * 1000 })
  return { Authorization: `Bearer ${issued.access_token}` }
}

export function fetchScenario(seed?: number): Promise<Scenario> {
  const query = seed === undefined ? '' : `?seed=${encodeURIComponent(seed)}`
  return request<Scenario>(`/api/v1/scenarios${query}`)
}

export async function fetchDecision(scenario: Scenario): Promise<Decision> {
  return request<Decision>('/api/v1/decisions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
    body: JSON.stringify({ scenario }),
  })
}

/** Records a disposition for a persisted decision. The backend answers 409 for a blocked
 * decision or when the approver is the proposer, and 403 when the role cannot approve —
 * those are safety rules, not bugs, and callers must not paper over them. */
export async function submitDisposition(
  decisionId: number,
  action: DispositionAction,
  reason: string,
): Promise<DispositionResult> {
  return request<DispositionResult>(`/api/v1/decisions/${decisionId}/disposition`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
    body: JSON.stringify({ action, reason }),
  })
}
