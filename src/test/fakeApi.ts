import { vi } from 'vitest'

export type Routes = Record<string, unknown | ((init?: RequestInit) => unknown)>

/** Replace fetch with canned JSON per "METHOD /path" (query string ignored unless listed). */
export function fakeApi(routes: Routes) {
  const calls: string[] = []
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input))
    const method = init?.method ?? 'GET'
    const key = `${method} ${url.pathname}`
    calls.push(`${key}${url.search}`)
    const route = routes[`${key}${url.search}`] ?? routes[key]
    if (route === undefined) return new Response(JSON.stringify({ detail: `no fake for ${key}` }), { status: 404 })
    const body = typeof route === 'function' ? (route as (init?: RequestInit) => unknown)(init) : route
    if (body instanceof Response) return body
    return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })
  })
  vi.stubGlobal('fetch', fetchMock)
  return { calls, fetchMock }
}

export const TOKEN = { access_token: 't', expires_in: 3600 }
