import type { Decision, Scenario, Severity } from '../types'
import { Panel } from './Panel'
import { Metric } from './Metric'
import { StatusBadge } from './StatusBadge'

const SEVERITY_ORDER: Severity[] = ['critical', 'high', 'medium', 'low']
const SEVERITY_DOT: Record<Severity, string> = {
  critical: 'bg-sev-critical',
  high: 'bg-sev-high',
  medium: 'bg-sev-medium',
  low: 'bg-sev-low',
}

interface SituationOverviewProps {
  scenario: Scenario
  decision: Decision | null
}

/** At-a-glance situation summary — every number here is a direct count/sum
 * over the already-fetched scenario (and decision, once one exists). Nothing
 * is estimated or fabricated; this only makes existing data faster to read. */
export function SituationOverview({ scenario, decision }: SituationOverviewProps) {
  const severityCounts = scenario.incidents.reduce(
    (counts, incident) => {
      counts[incident.severity] += 1
      return counts
    },
    { critical: 0, high: 0, medium: 0, low: 0 } as Record<Severity, number>,
  )
  const peopleAffected = scenario.incidents.reduce((sum, incident) => sum + incident.people_affected, 0)
  const availableResources = scenario.resources.filter((resource) => resource.available).length

  return (
    <Panel className="mb-5">
      <p className="eyebrow">Situation overview</p>
      <div className="mt-3 flex flex-wrap gap-x-8 gap-y-4">
        <Metric
          label="Incidents"
          value={
            <span className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className="text-lg font-semibold text-ink-900">{scenario.incidents.length}</span>
              <span className="flex flex-wrap gap-x-2 text-xs font-normal text-ink-600">
                {SEVERITY_ORDER.filter((severity) => severityCounts[severity] > 0).map((severity) => (
                  <span key={severity} className="inline-flex items-center gap-1">
                    <span className={`h-1.5 w-1.5 rounded-full ${SEVERITY_DOT[severity]}`} aria-hidden="true" />
                    {severityCounts[severity]} {severity}
                  </span>
                ))}
              </span>
            </span>
          }
        />
        <Metric label="People affected" value={<span className="text-lg font-semibold text-ink-900">{peopleAffected}</span>} />
        <Metric
          label="Resources available"
          value={
            <span className="text-lg font-semibold text-ink-900">
              {availableResources} / {scenario.resources.length}
            </span>
          }
        />
        {decision && (
          <Metric
            label="Unmet requirements"
            value={<span className="text-lg font-semibold text-ink-900">{decision.unmet_requirements.length}</span>}
          />
        )}
        {decision && (
          <Metric
            label="Advisory status"
            value={
              <StatusBadge tone={decision.status === 'blocked' ? 'blocked' : 'review'}>
                {decision.status === 'blocked' ? 'Blocked' : 'Ready for review'}
              </StatusBadge>
            }
          />
        )}
      </div>
    </Panel>
  )
}
