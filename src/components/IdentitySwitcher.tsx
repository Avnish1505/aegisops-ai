import { useState } from 'react'
import { DEV_AUTH, DEV_IDENTITIES, setIdentity } from '../api'

/** Development-only "acting as" control. Hidden unless dev sign-in is enabled. */
export function IdentitySwitcher() {
  const [sub, setSub] = useState(DEV_IDENTITIES[0].sub)
  if (!DEV_AUTH) return null
  return (
    <label className="inline-flex items-center gap-2 text-xs text-ink-600">
      <span>Acting as</span>
      <select
        value={sub}
        onChange={(event) => {
          const next = DEV_IDENTITIES.find((identity) => identity.sub === event.target.value)
          if (!next) return
          setIdentity(next)
          setSub(next.sub)
        }}
        className="border border-ink-300 bg-paper-sunken px-2 py-1 text-xs text-ink-800"
      >
        {DEV_IDENTITIES.map((identity) => (
          <option key={identity.sub} value={identity.sub}>
            {identity.label}
          </option>
        ))}
      </select>
    </label>
  )
}
