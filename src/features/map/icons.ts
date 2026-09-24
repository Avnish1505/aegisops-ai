import type { Severity } from '../../types'

/**
 * One icon atlas drawn at runtime: white shapes used as masks, so deck.gl colours them per
 * feature. Incidents use the severity shapes of SeverityGlyph; units are small squares.
 */
export type IconName = Severity | 'unit' | 'unit-unavailable'

const SIZE = 64
const NAMES: IconName[] = ['critical', 'high', 'medium', 'low', 'unit', 'unit-unavailable']

export const ICON_MAPPING = Object.fromEntries(
  NAMES.map((name, index) => [name, { x: index * SIZE, y: 0, width: SIZE, height: SIZE, mask: true }]),
) as Record<IconName, { x: number; y: number; width: number; height: number; mask: boolean }>

export function iconAtlas(): HTMLCanvasElement {
  const canvas = document.createElement('canvas')
  canvas.width = SIZE * NAMES.length
  canvas.height = SIZE
  const ctx = canvas.getContext('2d')
  if (!ctx) return canvas
  ctx.fillStyle = '#fff'
  ctx.strokeStyle = '#fff'
  const at = (index: number, draw: () => void) => {
    ctx.save()
    ctx.translate(index * SIZE, 0)
    ctx.beginPath()
    draw()
    ctx.restore()
  }
  at(0, () => { // diamond
    ctx.moveTo(32, 4); ctx.lineTo(60, 32); ctx.lineTo(32, 60); ctx.lineTo(4, 32); ctx.closePath(); ctx.fill()
  })
  at(1, () => { // triangle
    ctx.moveTo(32, 6); ctx.lineTo(60, 56); ctx.lineTo(4, 56); ctx.closePath(); ctx.fill()
  })
  at(2, () => { // filled circle
    ctx.arc(32, 32, 24, 0, Math.PI * 2); ctx.fill()
  })
  at(3, () => { // outlined circle
    ctx.lineWidth = 8; ctx.arc(32, 32, 22, 0, Math.PI * 2); ctx.stroke()
  })
  at(4, () => { // unit: filled square
    ctx.rect(14, 14, 36, 36); ctx.fill()
  })
  at(5, () => { // unavailable unit: outlined square
    ctx.lineWidth = 7; ctx.rect(16, 16, 32, 32); ctx.stroke()
  })
  return canvas
}
