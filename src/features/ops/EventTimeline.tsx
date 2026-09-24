import { Link } from '@tanstack/react-router'
import { useEvents } from '../../api/queries'
import { Mono, Panel } from '../../components/ui/Panel'
import { eventText } from '../../lib/events'
import { istClock } from '../../lib/time'


export function EventTimeline() {
  const events = useEvents(undefined, 30)
  return (
    <Panel title="Audit timeline" labelledBy="timeline-title" className="[grid-area:timeline]">
      {events.isError && <p className="px-3 py-2 text-sm text-high">Could not load events: {events.error.message}</p>}
      <ol className="text-sm">
        {events.data?.map((event) => {
          const decisionId = typeof event.payload.decision_id === 'number' ? event.payload.decision_id : undefined
          const verdict = typeof event.payload.verdict === 'string' ? event.payload.verdict : undefined
          const action = typeof event.payload.action === 'string' ? event.payload.action : undefined
          return (
            <li key={event.id} className="flex items-center gap-3 border-b border-divider px-3 py-1">
              <Mono>{istClock(new Date(event.ts))}</Mono>
              <span className="w-40 shrink-0">{eventText(event.type)}</span>
              <span className="w-28 shrink-0 truncate text-muted">{event.actor}</span>
              {verdict === 'blocked' && <span className="font-semibold text-blocked">BLOCKED</span>}
              {action && <span className="text-muted">{action}</span>}
              {decisionId !== undefined && (
                <Link to="/plans/$decisionId" params={{ decisionId }} className="underline">
                  Plan {decisionId}
                </Link>
              )}
              <Mono className="ml-auto" >#{event.id} {event.hash.slice(0, 10)}</Mono>
            </li>
          )
        })}
        {events.data?.length === 0 && <li className="px-3 py-2 text-muted">No events yet.</li>}
      </ol>
    </Panel>
  )
}
