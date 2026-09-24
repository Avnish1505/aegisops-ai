import { describe, expect, it } from 'vitest'
import { findQuotes, parseMismatches, segments } from './text'

describe('quote highlighting', () => {
  const report = 'Charbagh station ke peeche kamar tak pani, lagbhag 35 log   chhat par fanse hain.'

  it('finds each quote regardless of case and spacing, in order', () => {
    const ranges = findQuotes(report, [
      { quote: 'LAGBHAG 35 log chhat', label: 'people' },
      { quote: 'Charbagh station', label: 'location' },
      { quote: 'not in the report', label: 'ghost' },
    ])
    expect(ranges.map((r) => [r.label, report.slice(r.start, r.end)])).toEqual([
      ['location', 'Charbagh station'],
      ['people', 'lagbhag 35 log   chhat'],
    ])
  })

  it('splits text into plain and labelled segments', () => {
    const parts = segments('abc def ghi', [{ start: 4, end: 7, label: 'x' }])
    expect(parts).toEqual([{ text: 'abc ' }, { text: 'def', label: 'x' }, { text: ' ghi' }])
  })
})

describe('verifier mismatch parsing', () => {
  it('reads line and written number from both message forms, with or without a draft id', () => {
    expect(
      parseMismatches([
        'sitrep-1 line 4: RES-A ETA for INC-1 is 9.4, draft says 5.0',
        'line 7: 42 is not attributable to a known fact',
        'something else',
      ]),
    ).toEqual([
      { line: 4, written: '5.0', message: 'line 4: RES-A ETA for INC-1 is 9.4, draft says 5.0' },
      { line: 7, written: '42', message: 'line 7: 42 is not attributable to a known fact' },
    ])
  })
})
