import type { Severity } from '../types'

export const severityConfig: Record<Severity, { label: string; dot: string; text: string }> = {
  low: { label: 'Low', dot: 'bg-sev-low', text: 'text-sev-low' },
  medium: { label: 'Medium', dot: 'bg-sev-medium', text: 'text-sev-medium' },
  high: { label: 'High', dot: 'bg-sev-high', text: 'text-sev-high' },
  critical: { label: 'Critical', dot: 'bg-sev-critical', text: 'text-sev-critical' },
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  const style = severityConfig[severity]
  return (
    <span className={`inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider ${style.text}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${style.dot}`} aria-hidden="true" />
      {style.label}
    </span>
  )
}
