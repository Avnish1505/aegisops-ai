import { applyTheme, useTheme, type ThemeChoice } from '../../lib/theme'

const LABELS: Record<ThemeChoice, string> = { system: 'System', dark: 'Dark', light: 'Light' }

export function ThemeToggle() {
  const theme = useTheme()
  return (
    <label className="flex items-center gap-1.5 text-sm text-muted">
      <span>Theme</span>
      <select
        value={theme}
        onChange={(event) => applyTheme(event.target.value as ThemeChoice)}
        className="rounded-sm border border-control-border bg-surface px-1.5 py-0.5 text-sm text-text"
      >
        {(Object.keys(LABELS) as ThemeChoice[]).map((choice) => (
          <option key={choice} value={choice}>
            {LABELS[choice]}
          </option>
        ))}
      </select>
    </label>
  )
}
