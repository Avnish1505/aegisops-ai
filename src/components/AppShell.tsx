import type { ReactNode } from 'react'

interface AppShellProps {
  statusLine: ReactNode
  children: ReactNode
}

/** Top-level product shell: identity + ambient system status in the header,
 * the operational workspace below it. Kept compact — no decorative branding. */
export function AppShell({ statusLine, children }: AppShellProps) {
  return (
    <div className="min-h-screen bg-paper text-ink-800">
      <header className="border-b border-ink-300 bg-paper-raised">
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center justify-between gap-3 px-6 py-4">
          <div className="flex items-center gap-3">
            <div
              className="flex h-8 w-8 items-center justify-center border border-accent-700/50 bg-accent-100 font-mono text-sm font-bold text-accent-700"
              aria-hidden="true"
            >
              A
            </div>
            <div>
              <h1 className="text-base font-semibold tracking-tight text-ink-900">
                AegisOps <span className="text-ink-500">AI</span>
              </h1>
              <p className="text-[10px] uppercase tracking-[0.16em] text-ink-500">Crisis decision support · research exercise</p>
            </div>
          </div>
          {statusLine}
        </div>
      </header>
      <main className="mx-auto max-w-[1600px] px-6 py-6">{children}</main>
    </div>
  )
}
