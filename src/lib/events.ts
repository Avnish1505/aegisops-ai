/** Display names for audit event types (aegisops/audit/event_log.py callers). */
export const EVENT_TEXT: Record<string, string> = {
  decision_created: 'Plan proposed',
  verification_completed: 'Plan verified',
  disposition_recorded: 'Decision recorded',
  drafts_generated: 'Drafts generated',
  reverification_run: 'Re-verified from stored inputs',
  intake_received: 'Report received',
  intake_read: 'Report read by the model',
  intake_confirmed: 'Report fields confirmed',
  intake_dismissed: 'Report dismissed',
  intake_merged: 'Report merged as duplicate',
}

export function eventText(type: string): string {
  return EVENT_TEXT[type] ?? type.replace(/_/g, ' ')
}
