import { useEffect, useRef } from 'react'

export type HotkeyMap = Record<string, (event: KeyboardEvent) => void>

/** True when a keystroke belongs to a text field rather than to the console. */
export function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  if (target.isContentEditable) return true
  return ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)
}

/**
 * Single keys ("j", "Enter", "?") fire only when no text field has focus and no modifier is held;
 * "mod+k" means Cmd+K on macOS and Ctrl+K elsewhere and fires even while typing.
 */
export function useHotkeys(map: HotkeyMap, enabled = true): void {
  const latest = useRef(map)
  useEffect(() => {
    latest.current = map
  })
  useEffect(() => {
    if (!enabled) return
    const onKey = (event: KeyboardEvent) => {
      if (event.defaultPrevented) return
      const mod = event.metaKey || event.ctrlKey
      const name = mod ? `mod+${event.key.toLowerCase()}` : event.key.length === 1 ? event.key.toLowerCase() : event.key
      const handler = latest.current[name]
      if (!handler) return
      if (!mod && (event.altKey || isTyping(event.target))) return
      event.preventDefault()
      handler(event)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [enabled])
}
