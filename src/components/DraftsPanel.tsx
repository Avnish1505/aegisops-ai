import { useState } from 'react'
import { requestDrafts } from '../api'
import type { ReportDrafts } from '../types'
import { Panel } from './Panel'
import { StatusBadge } from './StatusBadge'
import { SecondaryButton } from './buttons'

/** SITREP and CAP drafts for review. Nothing here publishes; each draft states whether every
 * number in it passed the verifier. */
export function DraftsPanel({ decisionId }: { decisionId: number }) {
  const [drafts, setDrafts] = useState<ReportDrafts | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const generate = async () => {
    setBusy(true)
    setError(null)
    try {
      setDrafts(await requestDrafts(decisionId))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not draft reports.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Panel>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="panel-heading">Report drafts</h3>
          <p className="mt-1 text-xs text-ink-500">ICS-201-style SITREP and a CAP 1.2 alert (status Draft). Never published from here.</p>
        </div>
        <SecondaryButton onClick={() => void generate()} disabled={busy}>
          {busy ? 'Drafting…' : 'Draft SITREP and CAP'}
        </SecondaryButton>
      </div>
      {error && <p role="alert" className="mt-2 text-xs text-status-blocked">{error}</p>}
      {drafts &&
        [drafts.sitrep, drafts.cap].map((draft) => (
          <div key={draft.kind} className="mt-3">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="font-semibold uppercase text-ink-800">{draft.kind}</span>
              <StatusBadge tone={draft.numbers_verified ? 'positive' : 'blocked'}>
                {draft.numbers_verified ? 'Numbers verified' : 'Numbers NOT verified — do not use'}
              </StatusBadge>
              <span className="text-ink-500">source: {draft.source}</span>
            </div>
            {!draft.numbers_verified && (
              <ul className="mt-1 list-disc pl-5 text-xs text-status-blocked">
                {draft.mismatches.map((mismatch) => <li key={mismatch}>{mismatch}</li>)}
              </ul>
            )}
            <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap bg-paper-sunken p-3 font-mono text-[11px] leading-5 text-ink-800">
              {draft.document}
            </pre>
          </div>
        ))}
    </Panel>
  )
}
