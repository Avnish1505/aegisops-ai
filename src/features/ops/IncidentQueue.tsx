import type { Labels } from '../../api/types'
import { Mono, Panel } from '../../components/ui/Panel'
import { SeverityGlyph } from '../../components/ui/SeverityGlyph'
import { RESOURCE_LABEL, incidentState, latestReportMin, reportedAtMs, type IncidentState } from '../../lib/incidents'
import { age } from '../../lib/time'
import type { Decision, Incident } from '../../types'

function StateText({ state }: { state: IncidentState }) {
  if (state.kind === 'unplanned') return <span className="text-muted">Not planned</span>
  if (state.kind === 'covered') {
    return <span className="text-muted">{state.assigned.length} assigned</span>
  }
  const short = state.unmet.map((u) => `${u.quantity} ${RESOURCE_LABEL[u.resource_type]}`).join(', ')
  const tone = state.unmet.some((u) => u.severity === 'critical') ? 'text-critical' : 'text-high'
  return <span className={`font-semibold ${tone}`}>Short: {short}</span>
}

export function IncidentQueue({
  incidents,
  plan,
  labels,
  selectedId,
  onSelect,
  exerciseStartMs,
  now,
}: {
  incidents: Incident[]
  plan: Pick<Decision, 'assignments' | 'unmet_requirements'> | undefined
  labels: Labels | undefined
  selectedId: string | undefined
  onSelect: (id: string) => void
  exerciseStartMs: number | undefined
  now: number
}) {
  const latestMin = latestReportMin(incidents)
  return (
    <Panel title={`Incidents · ${incidents.length}`} labelledBy="queue-title" className="[grid-area:queue]">
      <ul role="listbox" aria-labelledby="queue-title" aria-activedescendant={selectedId ? `incident-${selectedId}` : undefined} tabIndex={0} className="outline-none">
        {incidents.map((incident) => {
          const selected = incident.id === selectedId
          const place = labels?.incidents[incident.id]
          return (
            <li
              key={incident.id}
              id={`incident-${incident.id}`}
              role="option"
              aria-selected={selected}
              onClick={() => onSelect(incident.id)}
              className={`cursor-pointer border-b border-divider px-3 py-1.5 ${selected ? 'bg-raised shadow-[inset_2px_0_0_var(--focus)]' : 'hover:bg-raised'}`}
            >
              <div className="flex items-center gap-2">
                <SeverityGlyph severity={incident.severity} />
                <span className="truncate font-medium">{place ?? 'Unnamed location'}</span>
                <span className="ml-auto font-mono text-sm text-muted" title="Time since reported">
                  {exerciseStartMs !== undefined ? age(reportedAtMs(incident, exerciseStartMs, latestMin), now) : `T+${incident.reported_at_min} min`}
                </span>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <Mono>{incident.id}</Mono>
                <span className="text-muted">{incident.type.replace('_', ' ')}</span>
                <span className="ml-auto">
                  <StateText state={incidentState(incident, plan)} />
                </span>
              </div>
            </li>
          )
        })}
      </ul>
    </Panel>
  )
}
