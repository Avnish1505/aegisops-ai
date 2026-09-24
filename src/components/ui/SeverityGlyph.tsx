import type { Severity } from '../../types'

/** Severity is never colour alone: shape + colour + text (ISA-101; WCAG 1.4.1). */
export const SEVERITY_TEXT: Record<Severity, string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
}

const COLOUR: Record<Severity, string> = {
  critical: 'var(--critical)',
  high: 'var(--high)',
  medium: 'var(--muted)',
  low: 'var(--muted)',
}

export function SeverityShape({ severity, size = 12 }: { severity: Severity; size?: number }) {
  const fill = COLOUR[severity]
  return (
    <svg width={size} height={size} viewBox="0 0 12 12" aria-hidden="true" className="shrink-0">
      {severity === 'critical' && <path d="M6 0.5 L11.5 6 L6 11.5 L0.5 6 Z" fill={fill} />}
      {severity === 'high' && <path d="M6 1 L11.5 11 L0.5 11 Z" fill={fill} />}
      {severity === 'medium' && <circle cx="6" cy="6" r="4.5" fill={fill} />}
      {severity === 'low' && <circle cx="6" cy="6" r="4" fill="none" stroke={fill} strokeWidth="1.5" />}
    </svg>
  )
}

export function SeverityGlyph({ severity, showLabel = true }: { severity: Severity; showLabel?: boolean }) {
  const alarm = severity === 'critical' || severity === 'high'
  return (
    <span
      className={`inline-flex items-center gap-1 text-sm ${alarm ? 'font-semibold' : 'text-muted'}`}
      style={alarm ? { color: COLOUR[severity] } : undefined}
    >
      <SeverityShape severity={severity} />
      {showLabel ? SEVERITY_TEXT[severity] : <span className="sr-only">{SEVERITY_TEXT[severity]}</span>}
    </span>
  )
}

/** Plan status: blocked is magenta with a square outline and the word, never colour alone. */
export function PlanStatus({ status }: { status: 'requires_human_approval' | 'blocked' }) {
  if (status === 'blocked') {
    return (
      <span className="inline-flex items-center gap-1 text-sm font-semibold text-blocked">
        <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
          <rect x="1" y="1" width="10" height="10" fill="none" stroke="currentColor" strokeWidth="2" />
        </svg>
        BLOCKED
      </span>
    )
  }
  return <span className="text-sm text-muted">Awaiting approval</span>
}
