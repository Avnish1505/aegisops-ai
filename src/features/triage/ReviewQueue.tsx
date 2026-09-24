import type { IntakeReport } from '../../api/types'
import { Mono, Panel } from '../../components/ui/Panel'
import { reasonText } from '../../lib/candidate'
import { age } from '../../lib/time'

const STATUS: Record<string, { text: string; alarm: boolean }> = {
  needs_review: { text: 'Needs review', alarm: true },
  ready: { text: 'Ready to confirm', alarm: false },
  unread: { text: 'Not read', alarm: false },
}

export function ReviewQueue({
  reports,
  selectedId,
  onSelect,
  now,
}: {
  reports: IntakeReport[]
  selectedId: number | undefined
  onSelect: (id: number) => void
  now: number
}) {
  return (
    <Panel title={`Reports · ${reports.length}`} labelledBy="triage-queue-title">
      <ul role="listbox" aria-labelledby="triage-queue-title" tabIndex={0} aria-activedescendant={selectedId ? `report-${selectedId}` : undefined} className="outline-none">
        {reports.map((report) => {
          const status = STATUS[report.status] ?? { text: report.status, alarm: false }
          const selected = report.id === selectedId
          return (
            <li
              key={report.id}
              id={`report-${report.id}`}
              role="option"
              aria-selected={selected}
              onClick={() => onSelect(report.id)}
              className={`cursor-pointer border-b border-divider px-3 py-1.5 ${selected ? 'bg-raised shadow-[inset_2px_0_0_var(--focus)]' : 'hover:bg-raised'}`}
            >
              <div className="flex items-center gap-2 text-sm">
                <span className={status.alarm ? 'inline-flex items-center gap-1 font-semibold text-high' : 'text-muted'}>
                  {status.alarm && <span aria-hidden="true">▲</span>}
                  {status.text}
                </span>
                <Mono className="ml-auto">#{report.id}</Mono>
                <span className="font-mono text-sm text-muted">{age(Date.parse(report.received_at), now)}</span>
              </div>
              <p className="truncate">{report.text}</p>
              {report.review_reasons.filter((r) => r !== 'not_read').slice(0, 2).map((reason) => (
                <p key={reason} className="truncate text-sm text-muted">{reasonText(reason)}</p>
              ))}
              {report.duplicates.length > 0 && (
                <p className="text-sm text-muted">Possible duplicate of {report.duplicates.map((d) => `#${d.id}`).join(', ')}</p>
              )}
            </li>
          )
        })}
        {reports.length === 0 && <li className="px-3 py-2 text-muted">No open reports.</li>}
      </ul>
    </Panel>
  )
}
