import type { ReactNode } from 'react'

export function Panel({
  title,
  actions,
  children,
  className = '',
  labelledBy,
}: {
  title: ReactNode
  actions?: ReactNode
  children: ReactNode
  className?: string
  labelledBy?: string
}) {
  return (
    <section aria-labelledby={labelledBy} className={`flex min-h-0 flex-col border border-divider bg-surface ${className}`}>
      <div className="flex h-8 shrink-0 items-center gap-2 border-b border-divider px-3">
        <h2 id={labelledBy} className="text-sm font-semibold uppercase tracking-wide text-muted">
          {title}
        </h2>
        <div className="ml-auto flex items-center gap-2">{actions}</div>
      </div>
      <div className="min-h-0 flex-1 overflow-auto">{children}</div>
    </section>
  )
}

export function Mono({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <span className={`font-mono text-sm text-muted ${className}`}>{children}</span>
}

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="rounded-sm border border-control-border px-1 font-mono text-xs text-muted">{children}</kbd>
  )
}

export function Notice({ tone = 'normal', children }: { tone?: 'normal' | 'high' | 'critical' | 'blocked'; children: ReactNode }) {
  const toneClass = {
    normal: 'border-divider text-muted',
    high: 'border-high text-high',
    critical: 'border-critical text-critical',
    blocked: 'border-blocked text-blocked',
  }[tone]
  return <div className={`border-l-2 px-3 py-2 text-sm ${toneClass}`}>{children}</div>
}

export function Button({
  children,
  onClick,
  disabled,
  type = 'button',
  className = '',
  ...rest
}: {
  children: ReactNode
  onClick?: () => void
  disabled?: boolean
  type?: 'button' | 'submit'
  className?: string
  'aria-describedby'?: string
  'aria-keyshortcuts'?: string
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex h-8 items-center justify-center gap-2 rounded border border-control-border bg-raised px-3 text-sm font-medium text-text hover:bg-bg disabled:cursor-not-allowed disabled:opacity-60 ${className}`}
      {...rest}
    >
      {children}
    </button>
  )
}
