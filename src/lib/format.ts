export const humanize = (value: string) => value.replace(/_/g, ' ')

export const shortId = (id: string) => (id.length > 13 ? `${id.slice(0, 13)}…` : id)
