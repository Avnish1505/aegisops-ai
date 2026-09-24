import type { Labels, StoredDecision } from '../../api/types'
import { Mono } from '../../components/ui/Panel'
import { QuotedText } from '../../components/ui/QuotedText'

export type QuotesByIncident = Record<string, { quote: string; label: string }[]>

/** Each incident's source report with the quote behind every extracted field marked. */
export function EvidencePanel({
  plan,
  labels,
  quotes,
}: {
  plan: StoredDecision
  labels: Labels | undefined
  quotes: QuotesByIncident
}) {
  const withReports = plan.scenario.incidents.filter((incident) => incident.report)
  return (
    <div className="space-y-3 p-3">
      {withReports.length === 0 && <p className="text-sm text-muted">No incident in this plan has a source report.</p>}
      {withReports.map((incident) => (
        <article key={incident.id} className="text-sm">
          <h4 className="font-medium">
            {labels?.incidents[incident.id] ?? 'Unnamed location'} <Mono>{incident.id}</Mono>
          </h4>
          <QuotedText text={incident.report ?? ''} quotes={quotes[incident.id] ?? []} />
          {!quotes[incident.id]?.length && <p className="text-xs text-muted">Seeded exercise inject: no model extraction, so no field quotes.</p>}
        </article>
      ))}
      {plan.evidence.length > 0 && (
        <section>
          <h4 className="font-medium">Retrieved evidence cited by the engine</h4>
          <ul className="list-disc pl-5 text-sm">
            {plan.evidence.map((item) => <li key={item.id}><Mono>{item.id}</Mono> {item.description}</li>)}
          </ul>
        </section>
      )}
    </div>
  )
}
