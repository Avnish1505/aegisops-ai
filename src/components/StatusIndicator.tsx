import type { ReactNode } from 'react'

interface StatusIndicatorProps {
  tone?: 'neutral' | 'positive' | 'negative'
  children: ReactNode
}

/** Dot + label used for ambient system-status language (header, live regions). */
export function StatusIndicator({ tone = 'neutral', children }: StatusIndicatorProps) {
  const dot = tone === 'positive' ? 'bg-status-available' : tone === 'negative' ? 'bg-status-blocked' : 'bg-accent-700'
  return (
    <span className="inline-flex items-center gap-2 text-xs text-ink-600">
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} aria-hidden="true" />
      {children}
    </span>
  )
}
