import { Outlet } from '@tanstack/react-router'
import { AUTH_MODE, IDENTITIES, signIn, useIdentity } from '../../lib/auth'
import { useLiveUpdates } from '../../lib/stream'
import { StatusBar } from './StatusBar'

export function RootLayout() {
  useLiveUpdates()
  const identity = useIdentity()
  return (
    <div className="flex h-screen flex-col bg-bg text-text">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:bg-raised focus:px-2"
      >
        Skip to content
      </a>
      <StatusBar />
      <main id="main" className="min-h-0 flex-1">
        {identity ? <Outlet /> : <SignIn />}
      </main>
    </div>
  )
}

export function NotFound() {
  return (
    <div className="p-6">
      <h1 className="text-lg font-semibold">Not found</h1>
      <p className="text-muted">There is no screen at this address.</p>
    </div>
  )
}

/** Every console API needs a token. Without a sign-in method nothing is requested. */
function SignIn() {
  const options = IDENTITIES[AUTH_MODE]
  return (
    <div className="max-w-xl p-6">
      <h1 className="text-lg font-semibold">Sign in</h1>
      {options.length === 0 ? (
        <p className="text-muted">
          This build has no sign-in method. Build with VITE_AUTH_MODE=dev (local API in development)
          or VITE_AUTH_MODE=demo (the public exercise sandbox). OIDC sign-in is not built.
        </p>
      ) : (
        <>
          <p className="mb-3 text-muted">
            Choose an exercise identity. Whoever proposes a plan cannot approve it, so the demo has
            an operator and a separate approver.
          </p>
          <ul className="space-y-2">
            {options.map((option) => (
              <li key={option.sub}>
                <button
                  type="button"
                  onClick={() => signIn(option)}
                  className="h-8 rounded border border-control-border bg-raised px-3 text-sm font-medium"
                >
                  {option.label}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
