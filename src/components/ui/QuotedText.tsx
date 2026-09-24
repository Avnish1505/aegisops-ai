import { findQuotes, segments } from '../../lib/text'

/**
 * Report text with each extracted field's quote marked. Marks are underlined and labelled, not
 * coloured: a quote is evidence, not an alarm.
 */
export function QuotedText({ text, quotes }: { text: string; quotes: { quote: string; label: string }[] }) {
  const parts = segments(text, findQuotes(text, quotes))
  return (
    <p className="whitespace-pre-wrap leading-6">
      {parts.map((part, index) =>
        part.label ? (
          <mark
            key={index}
            title={part.label}
            className="rounded-sm bg-raised px-0.5 text-text underline decoration-focus decoration-2 underline-offset-4"
          >
            {part.text}
            <sup className="ml-0.5 font-mono text-xs text-muted">{part.label}</sup>
          </mark>
        ) : (
          <span key={index}>{part.text}</span>
        ),
      )}
    </p>
  )
}
