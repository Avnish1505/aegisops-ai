import { Link } from '@tanstack/react-router'
import { useIdentity } from '../../lib/auth'
import { IdentityMenu } from './IdentityMenu'
import { IstClock } from './IstClock'
import { SystemStatus } from './SystemStatus'
import { ThemeToggle } from './ThemeToggle'

const NAV = [
  { to: '/', label: 'Operations' },
  { to: '/triage', label: 'Triage' },
  { to: '/evals', label: 'Evals' },
] as const

export function StatusBar() {
  const identity = useIdentity()
  return (
    <header className="flex h-9 shrink-0 items-center gap-4 border-b border-divider bg-surface px-3">
      <span className="rounded-sm border border-control-border px-1.5 text-xs font-semibold tracking-wider">
        EXERCISE
      </span>
            <nav aria-label="Main" className="flex gap-3 text-sm">
        {NAV.map((item) => (
          <Link
            key={item.to}
            to={item.to}
            className="text-muted hover:text-text [&.active]:text-text [&.active]:underline"
            activeOptions={{ exact: item.to === '/' }}
          >
            {item.label}
          </Link>
        ))}
      </nav>
      <div className="ml-auto flex items-center gap-4">
        {identity && <SystemStatus />}
        <IdentityMenu />
        <ThemeToggle />
        <IstClock />
      </div>
    </header>
  )
}
