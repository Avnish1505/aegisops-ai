/** Character ranges of ``needles`` in ``text`` (case-insensitive, whitespace-tolerant). */
export interface Range {
  start: number
  end: number
  label: string
}

function normalise(value: string): string {
  return value.normalize('NFKC').toLowerCase()
}

export function findQuotes(text: string, quotes: { quote: string; label: string }[]): Range[] {
  const haystack = normalise(text)
  const ranges: Range[] = []
  for (const { quote, label } of quotes) {
    const needle = normalise(quote).trim()
    if (!needle) continue
    const pattern = new RegExp(needle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\s+/g, '\\s+'), 'u')
    const match = pattern.exec(haystack)
    if (match) ranges.push({ start: match.index, end: match.index + match[0].length, label })
  }
  return ranges.sort((a, b) => a.start - b.start || b.end - a.end)
}

/** Split text into plain and highlighted segments; overlapping ranges merge into the first. */
export function segments(text: string, ranges: Range[]): { text: string; label?: string }[] {
  const out: { text: string; label?: string }[] = []
  let cursor = 0
  for (const range of ranges) {
    if (range.start < cursor) continue
    if (range.start > cursor) out.push({ text: text.slice(cursor, range.start) })
    out.push({ text: text.slice(range.start, range.end), label: range.label })
    cursor = range.end
  }
  if (cursor < text.length) out.push({ text: text.slice(cursor) })
  return out
}

export interface NumberProblem {
  line: number
  written: string
  message: string
}

/**
 * Parse the verifier's mismatch strings ("[draft-id ]line N: <claim> is <x>, draft says <y>" or
 * "[draft-id ]line N: <y> is not attributable to a known fact") into line + written number.
 */
export function parseMismatches(messages: string[]): NumberProblem[] {
  const problems: NumberProblem[] = []
  for (const message of messages) {
    const match = /line (\d+): (?:.* draft says (\S+)|(\S+) is not attributable)/.exec(message)
    if (match) problems.push({ line: Number(match[1]), written: match[2] ?? match[3], message: message.replace(/^\S+ (?=line \d+:)/, '') })
  }
  return problems
}
