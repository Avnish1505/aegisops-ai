import { Monitor, Moon, Sun } from 'lucide-react'
import { applyTheme, useTheme, type ThemeChoice } from '../../lib/theme'

const NEXT: Record<ThemeChoice, ThemeChoice> = { system: 'dark', dark: 'light', light: 'system' }
const ICON = { system: Monitor, dark: Moon, light: Sun }

export function ThemeToggle() {
  const theme = useTheme()
  const Icon = ICON[theme]
  return (
    <button
      type="button"
      onClick={() => applyTheme(NEXT[theme])}
      aria-label={`Theme: ${theme}. Switch to ${NEXT[theme]}.`}
      title={`Theme: ${theme}`}
      className="inline-flex h-6 w-6 items-center justify-center rounded-sm border border-control-border text-muted hover:text-text"
    >
      <Icon size={14} aria-hidden="true" />
    </button>
  )
}
