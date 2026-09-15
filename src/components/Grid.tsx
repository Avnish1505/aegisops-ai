import { useMemo } from 'react'
import type { KeyboardEvent } from 'react'
import type { Assignment, Decision, Scenario, SelectedEntity } from '../types'
import { humanize } from '../lib/format'

// Marker fills below are fixed hex values mirroring the sev.*/status.* tokens
// in tailwind.config.js — SVG fill/stroke attributes can't read Tailwind
// classes, so keep these in sync if the palette changes.
const SEV_CRITICAL = '#a13a24'
const SEV_HIGH = '#95541a'
const SEV_MEDIUM = '#8a6a12'
const SEV_LOW = '#2f5478'
const RESOURCE_AVAILABLE = '#3f6b46'
const RESOURCE_UNAVAILABLE = '#a89572'
const ROUTE_LINE = '#5b6f74'
const ROUTE_LINE_ACTIVE = '#241d13'

interface GridProps {
  scenario: Scenario
  decision: Decision | null
  selected: SelectedEntity
  activeAssignment: Assignment | null
  onSelect: (entity: SelectedEntity) => void
}

/** The scenario coordinate plane. Kept as an interactive SVG (not a decorative
 * map) — every marker is a real, selectable, keyboard-reachable entity. */
export function Grid({ scenario, decision, selected, activeAssignment, onSelect }: GridProps) {
  const incidentsById = useMemo(() => new Map(scenario.incidents.map((item) => [item.id, item])), [scenario])
  const resourcesById = useMemo(() => new Map(scenario.resources.map((item) => [item.id, item])), [scenario])
  const activeKey = activeAssignment ? `${activeAssignment.incident_id}:${activeAssignment.resource_id}` : null
  const point = ([x, y]: [number, number]) => ({ x, y: 100 - y })
  const isSelected = (kind: 'incident' | 'resource', id: string) => selected?.kind === kind && selected.entity.id === id
  const keyboardSelect = (event: KeyboardEvent<SVGGElement>, entity: SelectedEntity) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      onSelect(entity)
    }
  }

  return (
    <div className="relative overflow-hidden border border-ink-300 bg-paper-sunken">
      <svg viewBox="-7 -7 114 114" className="block aspect-[1.28/1] w-full" aria-label="Synthetic scenario coordinate grid">
        <defs>
          <pattern id="minorGrid" width="10" height="10" patternUnits="userSpaceOnUse">
            <path d="M 10 0 L 0 0 0 10" fill="none" stroke="#cdbfa0" strokeWidth="0.22" opacity="0.7" />
          </pattern>
        </defs>
        <rect x="0" y="0" width="100" height="100" fill="url(#minorGrid)" />
        <rect x="0" y="0" width="100" height="100" fill="none" stroke="#a89572" strokeWidth="0.4" />
        {[0, 20, 40, 60, 80, 100].map((tick) => (
          <g key={tick} fill="#7d6a49" fontSize="3" fontFamily="ui-monospace, SFMono-Regular, monospace">
            <text x={tick} y="105" textAnchor="middle">{tick}</text>
            <text x="-3" y={100 - tick + 1} textAnchor="end">{tick}</text>
          </g>
        ))}

        {decision?.assignments.map((assignment) => {
          const incident = incidentsById.get(assignment.incident_id)
          const resource = resourcesById.get(assignment.resource_id)
          if (!incident || !resource) return null
          const from = point(incident.location)
          const to = point(resource.location)
          const isActive = activeKey === `${assignment.incident_id}:${assignment.resource_id}`
          return (
            <line
              key={`${assignment.incident_id}-${assignment.resource_id}`}
              x1={from.x} y1={from.y} x2={to.x} y2={to.y}
              stroke={isActive ? ROUTE_LINE_ACTIVE : ROUTE_LINE}
              strokeWidth={isActive ? 1.1 : 0.38}
              opacity={isActive ? 1 : activeAssignment ? 0.18 : 0.55}
              className="transition-all duration-150"
            />
          )
        })}

        {scenario.resources.map((resource) => {
          const { x, y } = point(resource.location)
          const selectedResource = isSelected('resource', resource.id)
          return (
            <g
              key={resource.id}
              role="button"
              tabIndex={0}
              aria-label={`Resource ${resource.id}: ${humanize(resource.type)}, ${resource.available ? 'available' : 'unavailable'}`}
              className="cursor-pointer"
              onClick={() => onSelect({ kind: 'resource', entity: resource })}
              onKeyDown={(event) => keyboardSelect(event, { kind: 'resource', entity: resource })}
            >
              {selectedResource && <circle cx={x} cy={y} r="5" fill="none" stroke="#241d13" strokeWidth="0.5" />}
              <rect
                x={x - 2.1} y={y - 2.1} width="4.2" height="4.2" rx="0.4"
                fill={resource.available ? RESOURCE_AVAILABLE : RESOURCE_UNAVAILABLE}
                stroke="#fffdf8" strokeWidth="0.7"
                opacity={resource.available ? 1 : 0.55}
              />
              <path
                d={`M ${x - 1.05} ${y} H ${x + 1.05} M ${x} ${y - 1.05} V ${y + 1.05}`}
                stroke="#fffdf8" strokeWidth="0.45"
                opacity={resource.available ? 1 : 0.7}
              />
            </g>
          )
        })}

        {scenario.incidents.map((incident) => {
          const { x, y } = point(incident.location)
          const selectedIncident = isSelected('incident', incident.id)
          const fill =
            incident.severity === 'critical' ? SEV_CRITICAL
            : incident.severity === 'high' ? SEV_HIGH
            : incident.severity === 'medium' ? SEV_MEDIUM
            : SEV_LOW
          return (
            <g
              key={incident.id}
              role="button"
              tabIndex={0}
              aria-label={`Incident ${incident.id}: ${humanize(incident.type)}, ${incident.severity} severity`}
              className="cursor-pointer"
              onClick={() => onSelect({ kind: 'incident', entity: incident })}
              onKeyDown={(event) => keyboardSelect(event, { kind: 'incident', entity: incident })}
            >
              {incident.severity === 'critical' && (
                <circle cx={x} cy={y} r="5.2" fill="none" stroke={SEV_CRITICAL} strokeWidth="0.5" className="animate-beacon origin-center" />
              )}
              {selectedIncident && <circle cx={x} cy={y} r="5" fill="none" stroke="#241d13" strokeWidth="0.55" />}
              {incident.severity === 'critical' ? (
                <path d={`M ${x} ${y - 3.2} L ${x + 3.2} ${y} L ${x} ${y + 3.2} L ${x - 3.2} ${y} Z`} fill={fill} stroke="#fffdf8" strokeWidth="0.5" />
              ) : incident.severity === 'high' ? (
                <path d={`M ${x} ${y - 3} L ${x + 3} ${y + 2.3} L ${x - 3} ${y + 2.3} Z`} fill={fill} stroke="#fffdf8" strokeWidth="0.45" />
              ) : (
                <circle cx={x} cy={y} r={incident.severity === 'medium' ? '2.7' : '2.25'} fill={fill} stroke="#fffdf8" strokeWidth="0.6" />
              )}
            </g>
          )
        })}
      </svg>
      <div className="absolute bottom-2 left-2 flex flex-wrap gap-x-3 gap-y-1 border border-ink-300 bg-paper-raised/95 px-2.5 py-1.5 text-[10px] text-ink-600 shadow-soft">
        <span className="flex items-center gap-1"><span className="inline-block h-2 w-2 rotate-45" style={{ background: SEV_CRITICAL }} />Critical</span>
        <span className="flex items-center gap-1"><span className="inline-block h-2 w-2 rounded-full" style={{ background: SEV_HIGH }} />High</span>
        <span className="flex items-center gap-1"><span className="inline-block h-2 w-2 rounded-full" style={{ background: SEV_MEDIUM }} />Medium</span>
        <span className="flex items-center gap-1"><span className="inline-block h-2 w-2 rounded-full" style={{ background: SEV_LOW }} />Low</span>
        <span className="flex items-center gap-1"><span className="inline-block h-2 w-2" style={{ background: RESOURCE_AVAILABLE }} />Resource</span>
      </div>
    </div>
  )
}
