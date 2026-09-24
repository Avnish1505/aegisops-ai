import { describe, expect, it } from 'vitest'
import { age, istClock } from './time'

describe('time', () => {
  it('shows India Standard Time (UTC+05:30) regardless of the host zone', () => {
    expect(istClock(new Date('2026-09-24T06:30:05Z'))).toBe('12:00:05 IST')
  })

  it.each([
    [0, '0 min'],
    [59 * 60_000, '59 min'],
    [65 * 60_000, '1 h 05 min'],
    [3 * 24 * 3_600_000, '3 d'],
  ])('ages %i ms as %s', (elapsed, text) => {
    expect(age(0, elapsed)).toBe(text)
  })

  it('never shows a negative age for clock skew', () => {
    expect(age(10_000, 0)).toBe('0 min')
  })
})
