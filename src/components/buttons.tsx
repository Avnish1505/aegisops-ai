import type { ButtonHTMLAttributes } from 'react'

interface ActionButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  loading?: boolean
}

/** Primary call-to-action — one per surface (generate, get recommendation, approve). */
export function ActionButton({ loading, disabled, className = '', children, ...rest }: ActionButtonProps) {
  return (
    <button
      disabled={disabled || loading}
      className={`bg-accent-700 px-4 py-2 text-sm font-bold text-paper-raised transition-colors hover:bg-accent-600 active:bg-accent-800 disabled:cursor-wait disabled:opacity-60 ${className}`}
      {...rest}
    >
      {children}
    </button>
  )
}

interface SecondaryButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  tone?: 'neutral' | 'negative'
}

/** Lower-emphasis action — dismiss, reject, secondary navigation. */
export function SecondaryButton({ tone = 'neutral', className = '', children, ...rest }: SecondaryButtonProps) {
  const toneClasses =
    tone === 'negative'
      ? 'border-status-blocked/50 text-status-blocked hover:bg-status-blocked/10'
      : 'border-ink-300 text-ink-700 hover:bg-ink-100'
  return (
    <button className={`border px-3 py-2 text-xs font-bold transition-colors ${toneClasses} ${className}`} {...rest}>
      {children}
    </button>
  )
}
