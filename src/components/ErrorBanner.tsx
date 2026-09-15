interface ErrorBannerProps {
  message: string
  onDismiss: () => void
}

export function ErrorBanner({ message, onDismiss }: ErrorBannerProps) {
  return (
    <div role="alert" className="mb-5 flex items-start justify-between gap-4 border border-status-blocked/40 bg-status-blocked/10 p-4">
      <div>
        <p className="text-sm font-semibold text-status-blocked">API connection or validation error</p>
        <p className="mt-1 text-sm text-ink-700">{message}</p>
      </div>
      <button onClick={onDismiss} className="text-xs font-bold text-status-blocked underline underline-offset-4">
        Dismiss
      </button>
    </div>
  )
}
