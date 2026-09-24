import { useNavigate } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import { useIntake } from '../../api/queries'
import { Notice } from '../../components/ui/Panel'
import { useHotkeys } from '../../lib/hotkeys'
import type { IntakeReport } from '../../api/types'
import { ConfirmedPanel, FieldEditor } from './FieldEditor'
import { ReportDetail } from './ReportDetail'
import { ReviewQueue } from './ReviewQueue'

export function Triage({ selected }: { selected?: number }) {
  const navigate = useNavigate()
  const intake = useIntake()
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 30_000)
    return () => window.clearInterval(timer)
  }, [])
  const reports = intake.data ?? []
  const [confirmed, setConfirmed] = useState<IntakeReport | null>(null)
  const index = reports.findIndex((report) => report.id === selected)
  const current = index >= 0 ? reports[index] : undefined
  const select = (id: number) => void navigate({ to: '/triage', search: { report: id }, replace: true })

  useHotkeys({
    j: () => reports.length && select(reports[Math.min(reports.length - 1, index + 1)].id),
    k: () => reports.length && select(reports[Math.max(0, index - 1)].id),
    Enter: () => document.getElementById('editor-title')?.closest('section')?.querySelector<HTMLElement>('select, input')?.focus(),
  })

  if (intake.isError) return <div className="p-6"><Notice tone="high">Could not load reports: {intake.error.message}</Notice></div>

  return (
    <div className="grid h-full gap-px bg-divider" style={{ gridTemplateColumns: '360px minmax(0, 1fr) 420px' }}>
      <h1 className="sr-only">Intake triage</h1>
      <ReviewQueue reports={reports} selectedId={current?.id} onSelect={select} now={now} />
      {confirmed && confirmed.id === selected ? (
        <div className="col-span-2 min-h-0">
          <ConfirmedPanel report={confirmed} />
        </div>
      ) : current ? (
        <>
          <ReportDetail report={current} />
          <FieldEditor key={current.id} report={current} onConfirmed={setConfirmed} />
        </>
      ) : (
        <div className="col-span-2 bg-surface p-6 text-muted">Select a report (J / K).</div>
      )}
    </div>
  )
}
