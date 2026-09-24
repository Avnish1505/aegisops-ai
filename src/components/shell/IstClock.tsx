import { useEffect, useState } from 'react'
import { istClock } from '../../lib/time'

export function IstClock() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000)
    return () => window.clearInterval(timer)
  }, [])
  return (
    <time dateTime={now.toISOString()} className="font-mono text-sm" aria-label="Clock, India Standard Time">
      {istClock(now)}
    </time>
  )
}
