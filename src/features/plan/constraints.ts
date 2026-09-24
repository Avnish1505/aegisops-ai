import type { Labels } from '../../api/types'
import { RESOURCE_LABEL } from '../../lib/incidents'
import type { PlanningConstraint } from '../../types'

export function describeConstraint(constraint: PlanningConstraint, labels: Labels | undefined): string {
  switch (constraint.kind) {
    case 'reserve':
      return `Keep ${constraint.count} ${RESOURCE_LABEL[constraint.resource_type]}${constraint.count > 1 ? 's' : ''} unassigned inside ${constraint.zone.id}`
    case 'exclude_unit':
      return `Do not use ${labels?.units[constraint.unit_id] ?? 'unit'} (${constraint.unit_id})`
    case 'priority_boost':
      return `Weight ${labels?.incidents[constraint.incident_id] ?? 'incident'} (${constraint.incident_id}) ×${constraint.factor}`
  }
}
