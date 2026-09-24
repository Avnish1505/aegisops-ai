import '@fontsource/ibm-plex-mono/400.css'
import '@fontsource/ibm-plex-mono/500.css'
import '@fontsource/ibm-plex-sans/400.css'
import '@fontsource/ibm-plex-sans/500.css'
import '@fontsource/ibm-plex-sans/600.css'
import './index.css'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from '@tanstack/react-router'
import React from 'react'
import ReactDOM from 'react-dom/client'
import { initTheme } from './lib/theme'
import { createAppRouter } from './router'

initTheme()

const queryClient = new QueryClient({
  defaultOptions: {
    // Live updates arrive over SSE and invalidate queries; polling is a fallback only.
    queries: { staleTime: 15_000, retry: 1, refetchOnWindowFocus: false },
  },
})
const router = createAppRouter(queryClient)

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </React.StrictMode>,
)
