import { useSyncExternalStore } from 'react'
import { API_BASE_URL } from './config'
import { load, save } from './storage'

export type Role = 'viewer' | 'operator' | 'approver' | 'admin'

export interface Identity {
  sub: string
  role: Role
  label: string
}

/**
 * dev:  tokens from /api/v1/dev/token (API in development).
 * demo: fixed demo identities from /api/v1/demo/token (API in demo mode, resettable sandbox).
 * none: no sign-in UI; a real deployment needs OIDC, which is not built.
 */
export type AuthMode = 'dev' | 'demo' | 'none'

function modeFromEnv(): AuthMode {
  const configured = import.meta.env.VITE_AUTH_MODE
  if (configured === 'dev' || configured === 'demo' || configured === 'none') return configured
  // Backwards compatible with the M2 flag.
  return import.meta.env.DEV || import.meta.env.VITE_DEV_AUTH === 'true' ? 'dev' : 'none'
}

export const AUTH_MODE: AuthMode = modeFromEnv()

export const IDENTITIES: Record<AuthMode, Identity[]> = {
  // Two approvers, so the console can show that whoever proposes a plan cannot approve it.
  dev: [
    { sub: 'olive', role: 'operator', label: 'Olive · operator' },
    { sub: 'alice', role: 'approver', label: 'Alice · approver' },
    { sub: 'bob', role: 'approver', label: 'Bob · approver' },
  ],
  demo: [
    { sub: 'demo-operator', role: 'operator', label: 'Demo operator' },
    { sub: 'demo-approver', role: 'approver', label: 'Demo approver' },
  ],
  none: [],
}

const TOKEN_PATH: Record<AuthMode, string | null> = {
  dev: '/api/v1/dev/token',
  demo: '/api/v1/demo/token',
  none: null,
}

const STORAGE_KEY = 'aegisops.identity'
const listeners = new Set<() => void>()
let current: Identity | null =
  IDENTITIES[AUTH_MODE].find((identity) => identity.sub === load(STORAGE_KEY)) ?? null
const tokens = new Map<string, { token: string; expiresAt: number }>()

export function currentIdentity(): Identity | null {
  return current
}

export function signIn(identity: Identity | null): void {
  current = identity
  save(STORAGE_KEY, identity?.sub ?? null)
  listeners.forEach((listener) => listener())
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function useIdentity(): Identity | null {
  return useSyncExternalStore(subscribe, currentIdentity, currentIdentity)
}

export async function authHeader(): Promise<Record<string, string>> {
  const path = TOKEN_PATH[AUTH_MODE]
  if (!current || !path) return {}
  const cached = tokens.get(current.sub)
  if (cached && cached.expiresAt > Date.now()) return { Authorization: `Bearer ${cached.token}` }
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sub: current.sub, role: current.role }),
  })
  if (!response.ok) throw new Error(`Sign-in failed (${response.status}).`)
  const issued = (await response.json()) as { access_token: string; expires_in: number }
  // Refresh a minute early so a request never goes out with an expiring token.
  tokens.set(current.sub, {
    token: issued.access_token,
    expiresAt: Date.now() + (issued.expires_in - 60) * 1000,
  })
  return { Authorization: `Bearer ${issued.access_token}` }
}
