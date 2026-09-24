import { Link, useNavigate } from '@tanstack/react-router'
import { useState } from 'react'
import { Button, Mono, Notice, Panel } from '../../components/ui/Panel'
import { useIdentity } from '../../lib/auth'
import { downloadCsv, startTask, useCreateSession, useStudySession, useStudySessions, type StudyTask } from './api'

const UI_NAME = { legacy: 'the old console', console: 'the new console' }

export function StudyHome() {
  const sessions = useStudySessions()
  const create = useCreateSession()
  const navigate = useNavigate()
  const [participant, setParticipant] = useState('')
  const [csvError, setCsvError] = useState<string | null>(null)
  return (
    <div className="h-full overflow-auto p-4">
      <h1 className="text-lg font-semibold">User study</h1>
      <p className="max-w-3xl text-sm text-muted">
        Moderator page. Each participant reviews six plans in each interface (order and task set counterbalanced by
        participant number); three plans in each set carry one injected error. Protocol: <Mono>docs/USER_STUDY.md</Mono>.
      </p>
      <div className="mt-3 grid max-w-5xl grid-cols-1 gap-3 lg:grid-cols-2">
        <Panel title="New session" labelledBy="new-session-title">
          <form
            className="space-y-2 p-3"
            onSubmit={(event) => {
              event.preventDefault()
              create.mutate(participant.trim(), {
                onSuccess: (session) => void navigate({ to: '/study/$sessionId', params: { sessionId: session.id } }),
              })
            }}
          >
            <label className="block text-sm">
              Participant code (P01, P02, …; no names)
              <input value={participant} onChange={(e) => setParticipant(e.target.value)} className="mt-1 w-full rounded border border-control-border bg-bg px-2 py-1 text-sm" />
            </label>
            <Button type="submit" disabled={!/^P\d{2,3}$/.test(participant.trim()) || create.isPending}>
              {create.isPending ? 'Building 12 plans…' : 'Create session'}
            </Button>
            {create.isError && <Notice tone="high">{create.error.message}</Notice>}
          </form>
        </Panel>
        <Panel title="Sessions" labelledBy="sessions-title" actions={<Button onClick={() => downloadCsv().catch((e: Error) => setCsvError(e.message))}>Export CSV</Button>}>
          {csvError && <Notice tone="high">{csvError}</Notice>}
          <ul className="text-sm">
            {sessions.data?.map((s) => (
              <li key={s.id} className="flex items-center gap-3 border-b border-divider px-3 py-1">
                <Mono>{s.participant}</Mono>
                <span className="text-muted">{s.tasks.filter((t) => t.decided).length}/12 decided</span>
                <Link to="/study/$sessionId" params={{ sessionId: s.id }} className="ml-auto underline">Open runner</Link>
              </li>
            ))}
            {sessions.data?.length === 0 && <li className="px-3 py-2 text-muted">No sessions yet.</li>}
          </ul>
        </Panel>
      </div>
    </div>
  )
}

export function StudyRunner({ sessionId }: { sessionId: number }) {
  const session = useStudySession(sessionId)
  const identity = useIdentity()
  const navigate = useNavigate()
  const [opening, setOpening] = useState(false)
  if (session.isPending) return <p className="p-6 text-muted">Loading session…</p>
  if (session.isError) return <div className="p-6"><Notice tone="high">{session.error.message}</Notice></div>
  const current = session.data.tasks.find((task) => !task.decided)
  const done = session.data.tasks.filter((task) => task.decided).length

  const open = async (task: StudyTask) => {
    setOpening(true)
    await startTask(task.id)
    if (task.ui === 'legacy') window.location.assign(`/legacy/index.html?decision=${task.decision_id}`)
    else void navigate({ to: '/plans/$decisionId', params: { decisionId: task.decision_id }, search: { study: sessionId } })
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-6">
      <h1 className="text-lg font-semibold">Study · {session.data.participant}</h1>
      <p className="text-sm text-muted">{done} of 12 plans decided.</p>
      {identity?.role !== 'approver' && (
        <Notice tone="high">Sign in as an approver who did not propose these plans (for example Alice) before starting.</Notice>
      )}
      {current ? (
        <Panel title={`Plan ${current.order} of 12 · in ${UI_NAME[current.ui]}`} labelledBy="task-title">
          <div className="space-y-3 p-4">
            <p>
              Review the plan. <strong>Approve</strong> it if it is right. If something is wrong, <strong>reject</strong> it and choose
              the reason code that names the problem.
            </p>
            <p className="text-sm text-muted">
              The clock starts when you open the plan and stops when you record your decision. When you have decided, come back to
              this page{current.ui === 'legacy' ? ' (browser Back button)' : ' (the link at the top of the plan)'}.
            </p>
            <Button onClick={() => void open(current)} disabled={opening || identity?.role !== 'approver'}>
              Open plan {current.order}
            </Button>
          </div>
        </Panel>
      ) : (
        <Notice>All twelve plans are decided. Thank you. The moderator exports the results from the study page.</Notice>
      )}
    </div>
  )
}
