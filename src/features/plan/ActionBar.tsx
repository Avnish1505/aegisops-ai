import { Dialog } from 'radix-ui'
import { useState } from 'react'
import { useDisposition, useReasonCodes } from '../../api/queries'
import type { StoredDecision } from '../../api/types'
import { Button, Kbd, Notice } from '../../components/ui/Panel'
import { useIdentity } from '../../lib/auth'
import { useHotkeys } from '../../lib/hotkeys'
import { ApiError } from '../../lib/http'

type Action = 'approve' | 'reject'

/**
 * Approve and Reject have the same size and style: the console never nudges toward approval.
 * Both need a reason code; approval also needs an explicit confirmation step.
 */
export function ActionBar({ plan }: { plan: StoredDecision }) {
  const identity = useIdentity()
  const [open, setOpen] = useState<Action | null>(null)
  const decided = plan.approvals[plan.approvals.length - 1]
  const role = identity?.role
  const canDecide = role === 'operator' || role === 'approver' || role === 'admin'
  const isApprover = role === 'approver' || role === 'admin'
  const isProposer = identity?.sub === plan.proposer_sub
  const blocked = plan.status === 'blocked'

  const approveBlockedBy = decided
    ? null
    : blocked
      ? 'Blocked plans cannot be approved.'
      : !isApprover
        ? 'Approving needs the approver role.'
        : isProposer
          ? 'Proposer cannot approve: you proposed this plan.'
          : null
  const rejectBlockedBy = decided ? null : !canDecide ? 'Deciding needs the operator role or higher.' : null

  useHotkeys(
    {
      a: () => !approveBlockedBy && setOpen('approve'),
      r: () => !rejectBlockedBy && setOpen('reject'),
    },
    !decided && open === null,
  )

  return (
    <div className="sticky bottom-0 z-10 flex min-h-14 items-center gap-3 border-t border-divider bg-surface px-4 py-2">
      {decided ? (
        <p className="text-sm">
          <span className="font-semibold">{decided.action === 'approve' ? 'Approved' : 'Rejected'}</span> by {decided.actor}
          {decided.reason_code && <> · <span className="font-mono">{decided.reason_code}</span></>} ·{' '}
          <span className="text-muted">decisions are final; propose a new plan to change it</span>
        </p>
      ) : (
        <>
          <div className="flex gap-3">
            <Button
              className="w-36"
              disabled={Boolean(approveBlockedBy)}
              onClick={() => setOpen('approve')}
              aria-describedby="approve-note"
              aria-keyshortcuts="A"
            >
              Approve <Kbd>A</Kbd>
            </Button>
            <Button
              className="w-36"
              disabled={Boolean(rejectBlockedBy)}
              onClick={() => setOpen('reject')}
              aria-keyshortcuts="R"
            >
              Reject <Kbd>R</Kbd>
            </Button>
          </div>
          <p id="approve-note" className={`text-sm ${blocked ? 'font-semibold text-blocked' : 'text-muted'}`}>
            {approveBlockedBy ?? 'Approval records your name and reason in the audit log.'}
            {blocked && plan.verification.blocking_check_ids.length > 0 && (
              <> Failing: <span className="font-mono">{plan.verification.blocking_check_ids.join(', ')}</span></>
            )}
          </p>
          {rejectBlockedBy && <p className="text-sm text-muted">{rejectBlockedBy}</p>}
        </>
      )}
      {open && <DispositionDialog plan={plan} action={open} onClose={() => setOpen(null)} />}
    </div>
  )
}

function DispositionDialog({ plan, action, onClose }: { plan: StoredDecision; action: Action; onClose: () => void }) {
  const codes = useReasonCodes()
  const disposition = useDisposition(plan.decision_id)
  const [code, setCode] = useState('')
  const [text, setText] = useState('')
  const [confirming, setConfirming] = useState(false)
  const options = codes.data?.[action] ?? {}
  const needsText = code === 'other'
  const ready = Boolean(code) && (!needsText || text.trim().length > 0)
  const verb = action === 'approve' ? 'Approve' : 'Reject'

  const submit = () =>
    disposition.mutate(
      { action, reason_code: code, reason: text.trim() || undefined },
      { onSuccess: onClose },
    )

  return (
    <Dialog.Root open onOpenChange={(next) => !next && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/50" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[32rem] max-w-[calc(100vw-2rem)] -translate-x-1/2 -translate-y-1/2 space-y-3 border border-control-border bg-raised p-4 text-text">
          <Dialog.Title className="text-md font-semibold">
            {verb} plan <span className="font-mono">{plan.decision_id}</span>
          </Dialog.Title>
          {!confirming ? (
            <form
              className="space-y-3"
              onSubmit={(event) => {
                event.preventDefault()
                if (!ready) return
                if (action === 'approve') setConfirming(true)
                else submit()
              }}
            >
              <Dialog.Description className="text-sm text-muted">A reason code is required.</Dialog.Description>
              <fieldset className="space-y-1">
                <legend className="sr-only">Reason code</legend>
                {Object.entries(options).map(([value, label]) => (
                  <label key={value} className="flex items-start gap-2 text-sm">
                    <input type="radio" name="reason" value={value} checked={code === value} onChange={() => setCode(value)} className="mt-1" />
                    <span>
                      {label} <span className="font-mono text-xs text-muted">{value}</span>
                    </span>
                  </label>
                ))}
              </fieldset>
              <label className="block text-sm">
                Note {needsText ? '(required)' : '(optional)'}
                <textarea
                  value={text}
                  onChange={(event) => setText(event.target.value)}
                  rows={2}
                  maxLength={1000}
                  className="mt-1 w-full rounded border border-control-border bg-bg px-2 py-1 text-sm"
                />
              </label>
              {disposition.isError && <ErrorNote error={disposition.error} />}
              <div className="flex justify-end gap-2">
                <Dialog.Close asChild>
                  <Button>Cancel</Button>
                </Dialog.Close>
                <Button type="submit" disabled={!ready || disposition.isPending}>
                  {action === 'approve' ? 'Continue' : disposition.isPending ? 'Recording…' : 'Record rejection'}
                </Button>
              </div>
            </form>
          ) : (
            <div className="space-y-3">
              <Dialog.Description className="text-sm">
                Confirm approval of plan <span className="font-mono">{plan.decision_id}</span>: {plan.assignments.length} assignments,{' '}
                {plan.unmet_requirements.length} unmet requirement(s). Reason{' '}
                <span className="font-mono">{code}</span>. This is recorded under your name in the audit log. Nothing is dispatched.
              </Dialog.Description>
              {disposition.isError && <ErrorNote error={disposition.error} />}
              <div className="flex justify-end gap-2">
                <Button onClick={() => setConfirming(false)}>Back</Button>
                <Button onClick={submit} disabled={disposition.isPending}>
                  {disposition.isPending ? 'Recording…' : 'Confirm approval'}
                </Button>
              </div>
            </div>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

function ErrorNote({ error }: { error: Error }) {
  const refused = error instanceof ApiError && (error.status === 403 || error.status === 409)
  return <Notice tone={refused ? 'blocked' : 'high'}>{refused ? `Refused by the server: ${error.message}` : error.message}</Notice>
}
