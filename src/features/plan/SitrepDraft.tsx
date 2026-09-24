import { useDrafts } from '../../api/queries'
import type { StoredDecision } from '../../api/types'
import { Button, Notice } from '../../components/ui/Panel'
import { parseMismatches, type NumberProblem } from '../../lib/text'
import type { ReportDraft } from '../../types'

/** Draft text line by line; lines with a wrong number are marked and the number highlighted. */
export function DraftText({ text, problems }: { text: string; problems: NumberProblem[] }) {
  return (
    <pre className="overflow-x-auto whitespace-pre-wrap font-mono text-sm leading-5">
      {text.split('\n').map((line, index) => {
        const lineProblems = problems.filter((p) => p.line === index + 1)
        if (lineProblems.length === 0) return <div key={index}>{line || ' '}</div>
        const written = lineProblems[0].written
        const at = line.indexOf(written)
        return (
          <div key={index} className="border-l-2 border-critical pl-2" title={lineProblems.map((p) => p.message).join('\n')}>
            {at < 0 ? line : (
              <>
                {line.slice(0, at)}
                <mark className="bg-critical px-0.5 font-semibold text-on-alarm">{written}</mark>
                {line.slice(at + written.length)}
              </>
            )}
            <span className="sr-only"> Number does not match the plan: {lineProblems.map((p) => p.message).join('; ')}</span>
          </div>
        )
      })}
    </pre>
  )
}

function ModelDraft({ draft, title }: { draft: ReportDraft; title: string }) {
  return (
    <section className="space-y-1">
      <h4 className="text-sm font-semibold">
        {title} · {draft.source === 'llm' ? 'model prose' : 'template'} ·{' '}
        {draft.numbers_verified ? <span className="text-muted">numbers verified</span> : <span className="text-critical">NUMBERS NOT VERIFIED</span>}
      </h4>
      <DraftText text={draft.kind === 'cap' ? draft.text : draft.document} problems={parseMismatches(draft.mismatches)} />
      {draft.kind === 'cap' && (
        <details>
          <summary className="cursor-pointer text-sm">CAP 1.2 XML (status Draft, never published)</summary>
          <pre className="overflow-x-auto whitespace-pre-wrap font-mono text-xs text-muted">{draft.document}</pre>
        </details>
      )}
    </section>
  )
}

export function SitrepDraft({ plan }: { plan: StoredDecision }) {
  const drafts = useDrafts(plan.decision_id)
  const stored = plan.drafts[0]
  const check = plan.verification.checks.find((c) => c.id === 'draft_numbers_match_state')
  const problems = parseMismatches(check && !check.passed ? check.offending_ids : [])
  return (
    <div className="space-y-3 p-3">
      <p className="text-sm text-muted">Deterministic SITREP generated from the plan; every number is checked by the verifier. Nothing here is published.</p>
      {problems.length > 0 && <Notice tone="critical">{problems.length} number(s) in the SITREP do not match the plan.</Notice>}
      {stored ? <DraftText text={stored.text} problems={problems} /> : <p className="text-muted">No SITREP stored.</p>}
      <div className="border-t border-divider pt-2">
        <Button onClick={() => drafts.mutate()} disabled={drafts.isPending}>
          {drafts.isPending ? 'Drafting…' : 'Draft SITREP and CAP with the model'}
        </Button>
        {drafts.isError && <div className="mt-2"><Notice tone="high">{drafts.error.message}</Notice></div>}
        {drafts.data && (
          <div className="mt-2 space-y-3">
            <ModelDraft draft={drafts.data.sitrep} title="SITREP" />
            <ModelDraft draft={drafts.data.cap} title="CAP alert" />
          </div>
        )}
      </div>
    </div>
  )
}
