import { useReadStored, useStatus } from '../../api/queries'
import type { IntakeReport } from '../../api/types'
import { Button, Mono, Notice, Panel } from '../../components/ui/Panel'
import { QuotedText } from '../../components/ui/QuotedText'
import { SeverityGlyph } from '../../components/ui/SeverityGlyph'
import { useIdentity } from '../../lib/auth'
import { candidateQuotes, reasonText } from '../../lib/candidate'

export function ReportDetail({ report }: { report: IntakeReport }) {
  const identity = useIdentity()
  const llmOn = useStatus().data?.model.configured ?? false
  const read = useReadStored()
  const candidate = report.candidate
  const canAct = identity !== null && identity.role !== 'viewer'
  const alarms = report.review_reasons.filter((r) => r !== 'not_read')

  return (
    <Panel title={`Report #${report.id}`} labelledBy="report-title">
      <div className="space-y-3 p-3">
        <QuotedText text={report.text} quotes={candidateQuotes(candidate)} />
        {alarms.length > 0 && (
          <Notice tone="high">
            <ul>{alarms.map((reason) => <li key={reason}>▲ {reasonText(reason)}</li>)}</ul>
          </Notice>
        )}
        {candidate ? (
          <dl className="grid grid-cols-[8rem_1fr] gap-y-0.5 text-sm">
            <dt className="text-muted">Language</dt><dd>{candidate.language}</dd>
            <dt className="text-muted">Model reading</dt>
            <dd>
              {candidate.geocode ? `${candidate.geocode.name} (${candidate.geocode.method} match, OSM ${candidate.geocode.osm})` : 'no place'}
            </dd>
            <dt className="text-muted">Rule severity</dt>
            <dd className="flex items-center gap-2"><SeverityGlyph severity={candidate.severity} /> <span className="text-muted">{candidate.severity_rule}</span></dd>
            {report.read_meta && (
              <>
                <dt className="text-muted">Read by</dt>
                <dd><Mono>{report.read_meta.model}</Mono> · <Mono>{report.read_meta.prompt_version}</Mono>{report.source === 'demo_seed' && ' · recorded reading'}</dd>
              </>
            )}
          </dl>
        ) : (
          <div className="space-y-2">
            <p className="text-muted">Not read by the model yet, so there are no extracted fields or quotes.</p>
            {canAct && (
              <Button onClick={() => read.mutate(report.id)} disabled={!llmOn || read.isPending}>
                {read.isPending ? 'Reading…' : 'Read with the model'}
              </Button>
            )}
            {!llmOn && <p className="text-sm text-muted">The LLM is off on this server; fields can still be entered by hand.</p>}
            {read.isError && <Notice tone="high">{read.error.message}</Notice>}
          </div>
        )}
      </div>
    </Panel>
  )
}
