import type { ReactNode } from 'react'
import type { Assignment, Decision, Incident, Location, Resource, SelectedEntity, UnmetRequirement } from '../types'
import { humanize, shortId } from '../lib/format'
import { SeverityBadge } from './SeverityBadge'
import { StatusBadge } from './StatusBadge'
import { Metric } from './Metric'
import { EmptyState } from './EmptyState'

function EntityHeader({ id, title, badge }: { id: string; title: string; badge: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <div>
        <p className="font-mono text-xs text-accent-700">{id}</p>
        <p className="mt-1 text-sm font-semibold capitalize text-ink-900">{title}</p>
      </div>
      {badge}
    </div>
  )
}

function formatLocation(location: Location) {
  return `${location.lat.toFixed(5)}, ${location.lon.toFixed(5)}`
}

/** Relates the selected incident to the decision, when one has been requested:
 * either its proposed response (real assignments) or its still-unmet demand.
 * Nothing here is inferred — both lists come straight from the decision. */
function ProposedResponse({ assignments, unmet }: { assignments: Assignment[]; unmet: UnmetRequirement[] }) {
  if (assignments.length === 0 && unmet.length === 0) return null
  return (
    <div className="border-t border-ink-200 pt-3">
      <p className="metric-label">Proposed response</p>
      <div className="mt-1.5 space-y-1 text-xs">
        {assignments.map((assignment) => (
          <p key={assignment.resource_id} className="text-ink-800">
            <span className="font-mono text-accent-700">{shortId(assignment.resource_id)}</span>{' '}
            {humanize(assignment.resource_type)} · {assignment.travel_minutes.toFixed(1)} min travel
          </p>
        ))}
        {unmet.map((requirement) => (
          <p key={requirement.resource_type} className="text-sev-medium">
            {requirement.quantity} × {humanize(requirement.resource_type)} still unmet
          </p>
        ))}
      </div>
    </div>
  )
}

function IncidentDetail({ item, decision }: { item: Incident; decision: Decision | null }) {
  const assignments = decision?.assignments.filter((assignment) => assignment.incident_id === item.id) ?? []
  const unmet = decision?.unmet_requirements.filter((requirement) => requirement.incident_id === item.id) ?? []
  return (
    <div className="space-y-4">
      <EntityHeader id={item.id} title={humanize(item.type)} badge={<SeverityBadge severity={item.severity} />} />
      {item.report && (
        <blockquote className="border-l-2 border-ink-300 pl-3 text-xs leading-5 text-ink-700">
          <span className="metric-label block">Field report (untrusted text)</span>
          {item.report}
        </blockquote>
      )}
      <dl className="grid grid-cols-2 gap-x-3 gap-y-3 border-t border-ink-200 pt-3 text-xs">
        <Metric label="Lat, lon (WGS84)" value={<span className="font-mono">{formatLocation(item.location)}</span>} />
        <Metric label="Reported" value={`T+${item.reported_at_min} min`} />
        <Metric label="People affected" value={<span className="text-lg font-semibold">{item.people_affected}</span>} />
        <Metric
          label="Needs"
          value={
            <span className="space-y-0.5">
              {Object.entries(item.resources_needed).map(([type, count]) => (
                <span key={type} className="block">{count} × {humanize(type)}</span>
              ))}
            </span>
          }
        />
      </dl>
      {decision && <ProposedResponse assignments={assignments} unmet={unmet} />}
    </div>
  )
}

function ResourceDetail({ item, decision }: { item: Resource; decision: Decision | null }) {
  const assignment = decision?.assignments.find((candidate) => candidate.resource_id === item.id) ?? null
  return (
    <div className="space-y-4">
      <EntityHeader
        id={item.id}
        title={humanize(item.type)}
        badge={<StatusBadge tone={item.available ? 'available' : 'neutral'}>{item.available ? 'Available' : 'Unavailable'}</StatusBadge>}
      />
      <dl className="grid grid-cols-2 gap-x-3 gap-y-3 border-t border-ink-200 pt-3 text-xs">
        <Metric label="Lat, lon (WGS84)" value={<span className="font-mono">{formatLocation(item.location)}</span>} />
        <Metric label="Fallback speed" value={`${item.speed_kmh.toFixed(0)} km/h`} />
      </dl>
      {assignment && (
        <div className="border-t border-ink-200 pt-3">
          <p className="metric-label">Proposed response</p>
          <p className="mt-1.5 text-xs text-ink-800">
            Proposed for <span className="font-mono text-accent-700">{shortId(assignment.incident_id)}</span>{' '}
            · {assignment.travel_minutes.toFixed(1)} min travel
          </p>
        </div>
      )}
    </div>
  )
}

/** Entity inspector for whatever is selected on the grid. Surfaces the most
 * useful fields first (type/status, then key metrics) rather than every
 * field the backend happens to provide. When a decision exists, also relates
 * the entity to its proposed response or unmet demand. */
export function DetailPanel({ selected, decision }: { selected: SelectedEntity; decision: Decision | null }) {
  if (!selected) {
    return (
      <EmptyState
        title="Select an incident or resource marker to inspect its operational details."
        className="min-h-[185px]"
      />
    )
  }
  return selected.kind === 'incident' ? (
    <IncidentDetail item={selected.entity} decision={decision} />
  ) : (
    <ResourceDetail item={selected.entity} decision={decision} />
  )
}
