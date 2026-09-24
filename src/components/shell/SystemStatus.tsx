import { useEffect, useState } from 'react'
import { useStatus } from '../../api/queries'
import type { FeedHealth } from '../../api/types'
import { useLiveState, type LiveState } from '../../lib/stream'
import { age } from '../../lib/time'

const FEED_NAME: Record<FeedHealth['source'], string> = { sachet: 'SACHET', usgs: 'USGS', gdacs: 'GDACS' }

function useNow(intervalMs = 30_000): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), intervalMs)
    return () => window.clearInterval(timer)
  }, [intervalMs])
  return now
}

function Feed({ feed, now }: { feed: FeedHealth; now: number }) {
  const last = feed.last_ok_at ? age(Date.parse(feed.last_ok_at), now) : null
  const abnormal = feed.state === 'stale' || feed.state === 'failing'
  const text = {
    ok: last,
    stale: `stale ${last}`,
    failing: 'failing',
    no_data: 'no data',
  }[feed.state]
  const title = feed.state === 'failing' && feed.last_error ? `Last poll failed: ${feed.last_error}` : `Polls every ${feed.interval_min} min`
  return (
    <span title={title} className={`inline-flex items-center gap-1 text-sm ${abnormal ? 'font-semibold text-high' : 'text-muted'}`}>
      {abnormal && (
        <svg width="10" height="10" viewBox="0 0 12 12" aria-hidden="true">
          <path d="M6 1 L11.5 11 L0.5 11 Z" fill="currentColor" />
        </svg>
      )}
      <span className={abnormal ? '' : 'text-text'}>{FEED_NAME[feed.source]}</span>
      <span className="font-mono">{text}</span>
    </span>
  )
}

const LIVE_TEXT: Record<LiveState, string> = {
  signed_out: 'Not signed in',
  connecting: 'Connecting',
  live: 'Live',
  reconnecting: 'Reconnecting',
}

export function SystemStatus() {
  const status = useStatus()
  const live = useLiveState()
  const now = useNow()
  if (status.isError) {
    return <span className="text-sm font-semibold text-high">Status unavailable: {status.error.message}</span>
  }
  const data = status.data
  return (
    <div className="flex items-center gap-4" aria-label="System status">
      {data?.feeds.map((feed) => <Feed key={feed.source} feed={feed} now={now} />)}
      {data && (
        <span className="text-sm text-muted" title={data.model.configured ? data.model.model : 'No LLM key configured'}>
          LLM <span className="text-text">{data.model.configured ? 'on' : 'off'}</span>
        </span>
      )}
      {data && (
        <span className="text-sm text-muted" title="Plans awaiting a human decision">
          Pending <span className="font-mono font-semibold text-text">{data.pending_approvals}</span>
        </span>
      )}
      <span className={`text-sm ${live === 'reconnecting' ? 'font-semibold text-high' : 'text-muted'}`}>{LIVE_TEXT[live]}</span>
    </div>
  )
}
