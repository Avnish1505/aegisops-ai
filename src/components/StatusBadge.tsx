import type { ReactNode } from 'react'

export type BadgeTone = 'available' | 'blocked' | 'review' | 'neutral' | 'positive' | 'negative'

const toneClasses: Record<BadgeTone, string> = {
  available: 'border-status-available/40 bg-status-available/10 text-status-available',
  positive: 'border-status-available/40 bg-status-available/10 text-status-available',
  blocked: 'border-status-blocked/40 bg-status-blocked/10 text-status-blocked',
  negative: 'border-status-blocked/40 bg-status-blocked/10 text-status-blocked',
  review: 'border-accent-700/35 bg-accent-100 text-accent-700',
  neutral: 'border-ink-300 bg-ink-100 text-ink-600',
}

/** Small uppercase status pill. `tone` maps to the product's semantic palette —
 * see the color table in the design brief (available/blocked/human review). */
export function StatusBadge({ tone, children }: { tone: BadgeTone; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center rounded border px-2 py-1 text-[10px] font-bold uppercase tracking-wider ${toneClasses[tone]}`}
    >
      {children}
    </span>
  )
}
