import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { CONTRAST_REQUIREMENTS, THEMES, TOKEN_NAMES, contrastRatio } from './tokens'

// Read from disk: Vitest replaces imported CSS (even ?raw) with an empty string.
const css = readFileSync('src/design/theme.css', 'utf8')

function block(selector: string): Record<string, string> {
  const start = css.indexOf(selector)
  const body = css.slice(css.indexOf('{', start) + 1)
  const end = body.indexOf('}')
  return Object.fromEntries(
    [...body.slice(0, end).matchAll(/--([a-z-]+):\s*(#[0-9A-Fa-f]{6});/g)].map((m) => [m[1], m[2]]),
  )
}

describe('design tokens', () => {
  it.each(['dark', 'light'] as const)('%s theme meets every WCAG AA requirement', (theme) => {
    const failures = CONTRAST_REQUIREMENTS.filter(
      ([fg, bg, minimum]) => contrastRatio(THEMES[theme][fg], THEMES[theme][bg]) < minimum,
    ).map(([fg, bg, minimum]) => `${fg} on ${bg} < ${minimum}`)

    expect(failures).toEqual([])
  })

  it('theme.css matches tokens.ts for both themes', () => {
    expect(block(':root {')).toEqual(THEMES.dark) // first block: the dark default
    expect(block(":root[data-theme='light']")).toEqual(THEMES.light)
    expect(block(":root:not([data-theme='dark'])")).toEqual(THEMES.light)
  })

  it('every token exists in both themes', () => {
    for (const theme of Object.values(THEMES)) {
      expect(Object.keys(theme).sort()).toEqual([...TOKEN_NAMES].sort())
    }
  })

  it('computes the WCAG ratio for black on white as 21', () => {
    expect(contrastRatio('#000000', '#FFFFFF')).toBeCloseTo(21, 5)
  })
})
