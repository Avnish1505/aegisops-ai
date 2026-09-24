import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useSyncExternalStore } from 'react'
import { keys } from '../api/queries'
import { useIdentity } from './auth'
import { API_BASE_URL } from './config'
import { api } from './http'

export type LiveState = 'signed_out' | 'connecting' | 'live' | 'reconnecting'

const listeners = new Set<() => void>()
let state: LiveState = 'signed_out'

function setState(next: LiveState): void {
  state = next
  listeners.forEach((listener) => listener())
}

export function useLiveState(): LiveState {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    () => state,
    () => state,
  )
}

/** Which cached queries each server event makes stale. */
const INVALIDATES: Record<string, readonly (readonly unknown[])[]> = {
  'decision.created': [['decisions'], keys.status, ['events']],
  'decision.verified': [['decisions'], ['events']],
  'disposition.recorded': [['decisions'], ['decision'], keys.status, ['events']],
  'drafts.generated': [['events']],
  'intake.read': [['intake'], ['events']],
  'intake.updated': [['intake'], ['events']],
  'alert.ingested': [['alerts']],
  'feed.health': [keys.status],
}

/** One EventSource for the signed-in identity; reconnects with backoff (1 s .. 30 s). */
export function useLiveUpdates(): void {
  const client = useQueryClient()
  const identity = useIdentity()

  useEffect(() => {
    if (!identity || typeof EventSource === 'undefined') {
      setState('signed_out')
      return
    }
    let source: EventSource | null = null
    let timer: number | undefined
    let stopped = false
    let delay = 1000

    const retry = () => {
      if (stopped) return
      setState('reconnecting')
      timer = window.setTimeout(connect, delay)
      delay = Math.min(delay * 2, 30_000)
    }

    async function connect() {
      if (stopped) return
      setState(state === 'live' ? 'reconnecting' : 'connecting')
      let ticket: string
      try {
        ticket = (await api<{ ticket: string }>('/api/v1/stream/ticket', { method: 'POST' })).ticket
      } catch {
        retry()
        return
      }
      if (stopped) return
      source = new EventSource(`${API_BASE_URL}/api/v1/stream?ticket=${encodeURIComponent(ticket)}`)
      source.addEventListener('ready', () => {
        delay = 1000
        setState('live')
      })
      for (const [name, queryKeys] of Object.entries(INVALIDATES)) {
        source.addEventListener(name, () => {
          for (const queryKey of queryKeys) void client.invalidateQueries({ queryKey })
        })
      }
      source.onerror = () => {
        source?.close()
        source = null
        retry() // tickets are single-use, so every reconnect asks for a new one
      }
    }

    void connect()
    return () => {
      stopped = true
      window.clearTimeout(timer)
      source?.close()
    }
  }, [client, identity])
}
