/** localStorage for per-viewer conveniences only (theme, identity). It may be unavailable. */
export function load(key: string): string | null {
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}

export function save(key: string, value: string | null): void {
  try {
    if (value === null) window.localStorage.removeItem(key)
    else window.localStorage.setItem(key, value)
  } catch {
    // Private mode or blocked storage: the setting just won't persist.
  }
}
