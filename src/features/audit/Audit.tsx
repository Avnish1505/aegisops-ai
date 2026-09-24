import { Link } from '@tanstack/react-router'
import { useChain, useDecision, useEvents, useReverify } from '../../api/queries'
import type { AuditEvent } from '../../api/types'
import { Button, Mono, Notice, Panel } from '../../components/ui/Panel'
import { eventText } from '../../lib/events'
import { istClock, istDate } from '../../lib/time'


function Summary({ event }: { event: AuditEvent }) {
  const p = event.payload
  const text = (value: unknown) => (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean' ? String(value) : undefined)
  switch (event.type) {
    case 'decision_created':
      return <>engine <Mono>{text(p.engine)}</Mono>, status {text(p.status)}, scenario <Mono>{text(p.scenario_sha256)?.slice(0, 12)}</Mono></>
    case 'verification_completed':
      return <>verdict <span className={p.verdict === 'blocked' ? 'font-semibold text-blocked' : ''}>{text(p.verdict)}</span>{Array.isArray(p.failed_check_ids) && p.failed_check_ids.length > 0 && <>, failed <Mono>{p.failed_check_ids.join(', ')}</Mono></>}</>
    case 'disposition_recorded':
      return <>{text(p.action)} · <Mono>{text(p.reason_code)}</Mono>{p.reason ? <> · “{text(p.reason)}”</> : null}</>
    case 'reverification_run':
      return <>{p.matches ? 'matches the stored report' : <span className="font-semibold text-critical">differs: {Array.isArray(p.differing_checks) ? p.differing_checks.join(', ') : ''}</span>}</>
    default:
      return <Mono>{JSON.stringify(p).slice(0, 120)}</Mono>
  }
}

export function Audit({ decisionId }: { decisionId: number }) {
  const decision = useDecision(decisionId)
  const events = useEvents(decisionId, 200)
  const chain = useChain()
  const reverify = useReverify(decisionId)
  const ordered = [...(events.data ?? [])].reverse()

  return (
    <div className="h-full overflow-auto">
      <header className="flex items-center gap-4 border-b border-divider bg-surface px-4 py-2">
        <h1 className="text-lg font-semibold">
          Audit trail · plan <span className="font-mono">{decisionId}</span>
        </h1>
        <Link to="/plans/$decisionId" params={{ decisionId }} className="text-sm underline">Open plan</Link>
        {decision.data && <span className="text-sm text-muted">scenario SHA-256 <Mono>{decision.data.scenario_sha256.slice(0, 16)}…</Mono></span>}
      </header>
      <div className="grid grid-cols-1 gap-3 p-3 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <Panel title="Events for this plan (oldest first)" labelledBy="events-title">
          {events.isError && <p className="p-3 text-high">{events.error.message}</p>}
          <ol>
            {ordered.map((event) => (
              <li key={event.id} className="border-b border-divider px-3 py-2 text-sm">
                <div className="flex flex-wrap items-center gap-3">
                  <Mono>#{event.id}</Mono>
                  <Mono>{istDate(new Date(event.ts))} {istClock(new Date(event.ts))}</Mono>
                  <span className="font-medium">{eventText(event.type)}</span>
                  <span className="text-muted">by {event.actor}</span>
                </div>
                <div className="mt-0.5"><Summary event={event} /></div>
                <div className="mt-0.5 grid grid-cols-[4rem_1fr] font-mono text-xs text-muted">
                  <span>prev</span><span className="break-all">{event.prev_hash}</span>
                  <span>hash</span><span className="break-all text-text">{event.hash}</span>
                </div>
              </li>
            ))}
            {events.data?.length === 0 && <li className="p-3 text-muted">No events for this plan.</li>}
          </ol>
        </Panel>
        <div className="space-y-3">
          <Panel title="Hash chain" labelledBy="chain-title">
            <div className="space-y-2 p-3 text-sm">
              {chain.isPending && <p className="text-muted">Checking the whole chain…</p>}
              {chain.data?.ok && (
                <p>
                  Intact: <span className="font-mono">{chain.data.events_checked}</span> events, each hash covering the previous one. Head{' '}
                  <Mono className="break-all">{chain.data.head_hash}</Mono>
                </p>
              )}
              {chain.data && !chain.data.ok && chain.data.first_broken && (
                <Notice tone="critical">
                  Broken at event <span className="font-mono">#{chain.data.first_broken.event_id}</span>: {chain.data.first_broken.reason}
                </Notice>
              )}
              <p className="text-muted">
                Deleting the newest event is only detectable against a head hash kept elsewhere; note the head above.
              </p>
              <Button onClick={() => void chain.refetch()}>Check again</Button>
            </div>
          </Panel>
          <Panel title="Re-run the verifier" labelledBy="reverify-title">
            <div className="space-y-2 p-3 text-sm">
              <p className="text-muted">
                Re-solves and re-verifies from the stored scenario, travel matrix and constraints only (no OSRM, no model),
                then compares with the report stored at decision time. The run is itself recorded.
              </p>
              <Button onClick={() => reverify.mutate()} disabled={reverify.isPending}>
                {reverify.isPending ? 'Re-verifying…' : 'Re-verify stored inputs'}
              </Button>
              {reverify.isError && <Notice tone="high">{reverify.error.message}</Notice>}
              {reverify.data && (
                reverify.data.matches ? (
                  <p>
                    Same result as stored: verdict <span className="font-mono">{reverify.data.recomputed.verdict}</span>, all{' '}
                    {reverify.data.recomputed.checks.length} checks identical; scenario hash {reverify.data.scenario_sha256_matches ? 'matches' : 'DIFFERS'}.
                  </p>
                ) : (
                  <Notice tone="critical">
                    Differs from the stored report ({reverify.data.stored.verdict} stored, {reverify.data.recomputed.verdict} now):{' '}
                    <span className="font-mono">{reverify.data.differing_checks.join(', ') || 'details changed'}</span>
                  </Notice>
                )
              )}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  )
}
