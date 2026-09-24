import { Outlet } from '@tanstack/react-router'
import { StatusBar } from './StatusBar'

export function RootLayout() {
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
        <Outlet />
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
