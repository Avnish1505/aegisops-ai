import { AUTH_MODE, IDENTITIES, signIn, useIdentity } from '../../lib/auth'

/** "Acting as" for the dev and demo sign-in. A real deployment would use OIDC (not built). */
export function IdentityMenu() {
  const identity = useIdentity()
  const options = IDENTITIES[AUTH_MODE]
  if (options.length === 0) return null
  return (
    <label className="flex items-center gap-1.5 text-sm text-muted">
      <span className="sr-only">Acting as</span>
      <select
        value={identity?.sub ?? ''}
        onChange={(event) =>
          signIn(options.find((option) => option.sub === event.target.value) ?? null)
        }
        className="rounded-sm border border-control-border bg-surface px-1.5 py-0.5 text-sm text-text"
      >
        <option value="">Not signed in</option>
        {options.map((option) => (
          <option key={option.sub} value={option.sub}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  )
}
