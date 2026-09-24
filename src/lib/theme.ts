import { useSyncExternalStore } from 'react'
import { load, save } from './storage'

export type ThemeChoice = 'system' | 'dark' | 'light'

const KEY = 'aegisops.theme'
const listeners = new Set<() => void>()
let choice: ThemeChoice = parse(load(KEY))

function parse(value: string | null): ThemeChoice {
  return value === 'dark' || value === 'light' ? value : 'system'
}

export function applyTheme(next: ThemeChoice): void {
  choice = next
  save(KEY, next === 'system' ? null : next)
  if (next === 'system') document.documentElement.removeAttribute('data-theme')
  else document.documentElement.setAttribute('data-theme', next)
  listeners.forEach((listener) => listener())
}

export function useTheme(): ThemeChoice {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    () => choice,
    () => choice,
  )
}

/** Call before the first render so there is no flash of the wrong theme. */
export function initTheme(): void {
  applyTheme(choice)
}
