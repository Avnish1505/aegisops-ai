interface EmptyStateProps {
  eyebrow?: string
  title: string
  description?: string
  titleTag?: 'h2' | 'p'
  bordered?: boolean
  className?: string
}

/** Placeholder content for "nothing selected / nothing generated yet" states.
 * `titleTag="h2"` when the empty state is a real page section (e.g. the
 * pre-scenario landing state); the default `p` avoids adding a heading where
 * the copy is just an instruction (e.g. the unselected detail panel). */
export function EmptyState({
  eyebrow,
  title,
  description,
  titleTag = 'p',
  bordered = true,
  className = '',
}: EmptyStateProps) {
  const Title = titleTag
  return (
    <div
      className={`flex flex-col items-center justify-center text-center ${bordered ? 'border border-dashed border-ink-300' : ''} px-6 py-8 ${className}`}
    >
      {eyebrow && <p className="eyebrow">{eyebrow}</p>}
      <Title className={titleTag === 'h2' ? 'mt-2 text-xl font-semibold text-ink-900' : 'text-sm leading-6 text-ink-600'}>
        {title}
      </Title>
      {description && <p className="mt-2 max-w-md text-sm leading-6 text-ink-600">{description}</p>}
    </div>
  )
}
