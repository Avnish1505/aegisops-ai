import { authHeader } from './auth'
import { API_BASE_URL } from './config'

/** An HTTP error from the API. 403/409 on approvals are safety rules, not bugs: show `detail`. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string,
  ) {
    super(detail)
    this.name = 'ApiError'
  }
}

interface Options {
  method?: 'GET' | 'POST' | 'PATCH'
  body?: unknown
  auth?: boolean
  headers?: Record<string, string>
}

export async function raw(path: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(`${API_BASE_URL}${path}`, init)
  } catch {
    throw new ApiError(0, `Could not reach the AegisOps API at ${API_BASE_URL}.`)
  }
}

export async function errorFrom(response: Response): Promise<ApiError> {
  let detail = `Request failed (${response.status}).`
  try {
    const payload = (await response.json()) as { detail?: unknown }
    if (typeof payload.detail === 'string') detail = payload.detail
  } catch {
    // Non-JSON error body: the status line above is still useful.
  }
  return new ApiError(response.status, detail)
}

export async function api<T>(path: string, options: Options = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json', ...options.headers }
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'
  if (options.auth !== false) Object.assign(headers, await authHeader())
  const response = await raw(path, {
    method: options.method ?? 'GET',
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  })
  if (!response.ok) throw await errorFrom(response)
  return (await response.json()) as T
}
