import type { HTMLAttributes, ReactNode } from 'react'

interface PanelProps extends HTMLAttributes<HTMLElement> {
  children: ReactNode
  padded?: boolean
  as?: 'div' | 'aside' | 'section'
}

/** Base surface for structured content. Border-only by default — see the
 * "restrained shadows" rule; reach for `shadow-soft` only where something
 * genuinely needs to lift off the page. */
export function Panel({ children, padded = true, as = 'div', className = '', ...rest }: PanelProps) {
  const Tag = as
  return (
    <Tag className={`panel ${padded ? 'p-4' : ''} ${className}`} {...rest}>
      {children}
    </Tag>
  )
}
