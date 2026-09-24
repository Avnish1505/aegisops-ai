import { describe, expect, it } from 'vitest'
import { formatEstimate } from './Evals'

describe('estimate formatting', () => {
  it('shows the value, the bootstrap interval and n', () => {
    expect(formatEstimate({ value: 0.72, ci95: [0.651, 0.783], n: 200 })).toBe('72.0% [65.1, 78.3] (n = 200)')
    expect(formatEstimate({ value: 1.25, ci95: [1, 1.5], n: 9 }, false, 2)).toBe('1.25 [1.00, 1.50] (n = 9)')
  })

  it('says n/a instead of inventing a number', () => {
    expect(formatEstimate({ value: null, ci95: [null, null], n: 0 })).toBe('n/a')
  })
})
