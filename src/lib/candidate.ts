import type { IncidentCandidate } from '../api/types'
import { RESOURCE_LABEL } from './incidents'

/** Every grounded field's quote, labelled for the report highlighter. */
export function candidateQuotes(candidate: IncidentCandidate | null): { quote: string; label: string }[] {
  if (!candidate) return []
  return [
    ...(candidate.incident_type ? [{ quote: candidate.incident_type.quote, label: 'type' }] : []),
    ...(candidate.location_text ? [{ quote: candidate.location_text.quote, label: 'place' }] : []),
    ...(candidate.people_count ? [{ quote: candidate.people_count.quote, label: 'people' }] : []),
    ...candidate.needs.map((need) => ({ quote: need.quote, label: `need: ${RESOURCE_LABEL[need.resource_type]}` })),
    ...candidate.signals.map((signal) => ({ quote: signal.quote, label: signal.signal.replace('_', ' ') })),
  ]
}

export const REASON_TEXT: Record<string, string> = {
  not_read: 'Not read by the model yet',
  no_incident_type: 'No incident type',
  no_location: 'Place not found in the gazetteer',
  fuzzy_location: 'Place matched only approximately',
  instruction_like_text: 'Text reads like an instruction to the system',
}

export function reasonText(reason: string): string {
  if (reason.startsWith('field_dropped:')) {
    return `Dropped ${reason.slice('field_dropped:'.length).replace('_', ' ')}: its quote is not in the report`
  }
  return REASON_TEXT[reason] ?? reason
}
