import type { Labels, StoredDecision } from '../../api/types'
import { Mono } from '../../components/ui/Panel'
import { SeverityGlyph } from '../../components/ui/SeverityGlyph'
import { RESOURCE_LABEL, SEVERITY_RANK, minutes } from '../../lib/incidents'
import type { CheckResult } from '../../types'

/** Checks whose offending ids are unit ids, so they can be shown on the unit's row. */
const UNIT_CHECKS = new Set([
  'unit_exists', 'unit_available', 'unit_not_duplicated', 'capability_match', 'travel_time_matches', 'assignments_cited',
])

export function AssignmentsTable({ plan, labels }: { plan: StoredDecision; labels: Labels | undefined }) {
  const failed = plan.verification.checks.filter((check) => !check.passed && UNIT_CHECKS.has(check.id))
  const problems = (unitId: string): CheckResult[] => failed.filter((check) => check.offending_ids.includes(unitId))
  const incidents = [...plan.scenario.incidents].sort((a, b) => SEVERITY_RANK[b.severity] - SEVERITY_RANK[a.severity])
  const units = new Map(plan.scenario.resources.map((unit) => [unit.id, unit]))
  const provider = plan.travel_times.provider

  return (
    <table className="w-full border-collapse text-sm">
      <caption className="sr-only">Assignments by incident, with verified ETAs</caption>
      <thead className="text-left text-muted">
        <tr className="border-b border-divider">
          <th scope="col" className="py-1 pl-3 font-medium">Incident</th>
          <th scope="col" className="py-1 font-medium">Unit</th>
          <th scope="col" className="py-1 pr-3 text-right font-medium">ETA ({provider})</th>
        </tr>
      </thead>
      <tbody>
        {incidents.map((incident) => {
          const assigned = plan.assignments.filter((a) => a.incident_id === incident.id)
          const unmet = plan.unmet_requirements.filter((u) => u.incident_id === incident.id)
          const rows = Math.max(1, assigned.length + unmet.length)
          const head = (
            <th scope="row" rowSpan={rows} className="w-56 py-1 pl-3 text-left align-top font-normal">
              <div className="font-medium">{labels?.incidents[incident.id] ?? 'Unnamed location'}</div>
              <div className="flex items-center gap-2">
                <Mono>{incident.id}</Mono>
                <SeverityGlyph severity={incident.severity} />
              </div>
            </th>
          )
          return [
            ...assigned.map((assignment, index) => {
              const verified = plan.travel_times.minutes[assignment.resource_id]?.[incident.id]
              const issues = problems(assignment.resource_id)
              const etaWrong = issues.some((check) => check.id === 'travel_time_matches')
              const known = units.has(assignment.resource_id)
              return (
                <tr key={`${incident.id}-${assignment.resource_id}`} className="border-b border-divider align-top">
                  {index === 0 && head}
                  <td className="py-1">
                    <div>{known ? labels?.units[assignment.resource_id] ?? 'Unit' : <span className="font-semibold text-critical">Not in the scenario</span>} · {RESOURCE_LABEL[assignment.resource_type]}</div>
                    <Mono>{assignment.resource_id}</Mono>
                    {issues.map((check) => (
                      <div key={check.id} className="font-semibold text-critical">
                        ◆ {check.message.split(':')[0]}
                      </div>
                    ))}
                  </td>
                  <td className="py-1 pr-3 text-right font-mono">
                    {verified !== undefined ? minutes(verified) : '—'}
                    {etaWrong && (
                      <div className="font-semibold text-critical">plan claims {minutes(assignment.travel_minutes)}</div>
                    )}
                  </td>
                </tr>
              )
            }),
            ...unmet.map((item, index) => (
              <tr key={`${incident.id}-unmet-${item.resource_type}`} className="border-b border-divider">
                {assigned.length === 0 && index === 0 && head}
                <td colSpan={2} className={`py-1 pr-3 font-semibold ${item.severity === 'critical' ? 'text-critical' : 'text-high'}`}>
                  Unmet: {item.quantity} {RESOURCE_LABEL[item.resource_type]}
                </td>
              </tr>
            )),
            ...(assigned.length + unmet.length === 0
              ? [
                  <tr key={`${incident.id}-none`} className="border-b border-divider">
                    {head}
                    <td colSpan={2} className="py-1 text-muted">Nothing assigned or declared</td>
                  </tr>,
                ]
              : []),
          ]
        })}
      </tbody>
    </table>
  )
}
