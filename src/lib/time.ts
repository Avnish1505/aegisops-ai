/** India Standard Time (UTC+05:30, no daylight saving) for the header clock and timestamps. */
const IST = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Asia/Kolkata',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
})

const IST_DATE = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Asia/Kolkata',
  day: '2-digit',
  month: 'short',
})

export function istClock(now: Date): string {
  return `${IST.format(now)} IST`
}

export function istDate(now: Date): string {
  return IST_DATE.format(now)
}

/** "4 min", "1 h 05 min", "2 d": compact age for queues and feed health. */
export function age(fromMs: number, nowMs: number): string {
  const minutes = Math.max(0, Math.floor((nowMs - fromMs) / 60_000))
  if (minutes < 60) return `${minutes} min`
  const hours = Math.floor(minutes / 60)
  if (hours < 48) return `${hours} h ${String(minutes % 60).padStart(2, '0')} min`
  return `${Math.floor(hours / 24)} d`
}
