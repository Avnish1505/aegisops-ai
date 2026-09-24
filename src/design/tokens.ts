/**
 * Design tokens: the single source of colour values for CSS (src/design/theme.css, checked
 * against this file by tokens.test.ts) and for canvas/WebGL layers that cannot read CSS.
 *
 * ISA-101 high-performance HMI: a neutral grey canvas, and colour only for abnormal states.
 * Normal, medium, low and "OK" are grey. There is no green.
 */

export type ThemeName = 'dark' | 'light'

export const TOKEN_NAMES = [
  'bg', // canvas
  'surface', // panels
  'raised', // dialogs, menus, selected rows
  'divider', // decorative separators (not a control boundary)
  'control-border', // inputs, buttons: >= 3:1 against bg, surface and raised
  'text',
  'muted',
  'critical', // red
  'high', // amber
  'blocked', // magenta
  'focus',
  'on-alarm', // text drawn on a critical/high/blocked fill
] as const

export type TokenName = (typeof TOKEN_NAMES)[number]

export const THEMES: Record<ThemeName, Record<TokenName, string>> = {
  dark: {
    bg: '#1C1F23',
    surface: '#24282D',
    raised: '#2C3137',
    divider: '#3A4047',
    'control-border': '#7A828B',
    text: '#E4E7EA',
    muted: '#A7AEB6',
    critical: '#FF6B6B',
    high: '#F5B041',
    blocked: '#F17CF1',
    focus: '#7FB2FF',
    'on-alarm': '#1C1F23',
  },
  light: {
    bg: '#DCDEE1',
    surface: '#EEEFF1',
    raised: '#FFFFFF',
    divider: '#C3C7CC',
    'control-border': '#6B7279',
    text: '#15181B',
    muted: '#4A5057',
    critical: '#B3261E',
    high: '#8A5300',
    blocked: '#9C1F99',
    focus: '#1F5FBF',
    'on-alarm': '#FFFFFF',
  },
}

const BACKGROUNDS: TokenName[] = ['bg', 'surface', 'raised']

/** Pairs that must meet WCAG 2.2 AA: [foreground, background, minimum ratio]. */
export const CONTRAST_REQUIREMENTS: [TokenName, TokenName, number][] = [
  ...(['text', 'muted', 'critical', 'high', 'blocked'] as TokenName[]).flatMap((fg) =>
    BACKGROUNDS.map((bg): [TokenName, TokenName, number] => [fg, bg, 4.5]),
  ),
  ...BACKGROUNDS.map((bg): [TokenName, TokenName, number] => ['control-border', bg, 3]),
  ...BACKGROUNDS.map((bg): [TokenName, TokenName, number] => ['focus', bg, 3]),
  ...(['critical', 'high', 'blocked'] as TokenName[]).map(
    (fill): [TokenName, TokenName, number] => ['on-alarm', fill, 4.5],
  ),
]

function channel(value: number): number {
  const c = value / 255
  return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
}

export function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16))
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
}

export function contrastRatio(a: string, b: string): number {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (light + 0.05) / (dark + 0.05)
}

/** [r, g, b] for deck.gl layers. */
export function rgb(hex: string): [number, number, number] {
  return [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)) as [number, number, number]
}

export const FONT_SANS = '"IBM Plex Sans", ui-sans-serif, system-ui, sans-serif'
export const FONT_MONO = '"IBM Plex Mono", ui-monospace, "SFMono-Regular", monospace'
/** px; the scale steps are 11 / 12 / 13 (base) / 15 / 18. */
export const TYPE_SCALE = { xs: 11, sm: 12, base: 13, md: 15, lg: 18 } as const
