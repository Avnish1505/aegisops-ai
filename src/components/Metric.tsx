import type { ReactNode } from 'react'

interface MetricProps {
  label: string
  value: ReactNode
  valueClassName?: string
}

/** Label/value pair used throughout entity and decision detail panels. */
export function Metric({ label, value, valueClassName = 'text-ink-800' }: MetricProps) {
  return (
    <div>
      <p className="metric-label">{label}</p>
      <p className={`mt-1 ${valueClassName}`}>{value}</p>
    </div>
  )
}
