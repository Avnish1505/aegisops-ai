import type { ReactNode } from 'react'

interface SectionHeaderProps {
  eyebrow?: string
  title: string
  description?: string
  meta?: ReactNode
  as?: 'h2' | 'h3'
}

/** Eyebrow + heading + optional description, with a trailing meta/action slot.
 * Renders a real heading element so the page keeps a semantic outline. */
export function SectionHeader({ eyebrow, title, description, meta, as = 'h2' }: SectionHeaderProps) {
  const Heading = as
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <Heading className={`panel-heading ${eyebrow ? 'mt-1' : ''}`}>{title}</Heading>
        {description && <p className="mt-0.5 text-xs text-ink-500">{description}</p>}
      </div>
      {meta && <div className="shrink-0">{meta}</div>}
    </div>
  )
}
