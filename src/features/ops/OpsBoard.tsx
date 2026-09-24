import { useNavigate } from '@tanstack/react-router'
import { useEffect, useMemo, useState } from 'react'
import { useDecision, useDecisions, useExercise, useLabels, useStatus } from '../../api/queries'
import { Notice, Panel } from '../../components/ui/Panel'
import { useHotkeys } from '../../lib/hotkeys'
import { byPriority } from '../../lib/incidents'
import { EventTimeline } from './EventTimeline'
import { IncidentQueue } from './IncidentQueue'
import { Inspector } from './Inspector'

function useMinuteClock(): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 30_000)
    return () => window.clearInterval(timer)
  }, [])
  return now
}

export function OpsBoard({ mapSlot }: { mapSlot?: (props: MapSlotProps) => React.ReactNode }) {
  const navigate = useNavigate()
  const now = useMinuteClock()
  const status = useStatus()
  const exerciseId = status.data?.exercise?.id
  const exercise = useExercise(exerciseId)
  const scenario = exercise.data
  const latest = useDecisions({ scenario_id: scenario?.scenario_id, limit: 1 })
  const latestId = scenario ? latest.data?.[0]?.decision_id : undefined
  const plan = useDecision(latestId).data
  const labels = useLabels(scenario).data
  const startedAt = status.data?.exercise?.started_at
  const exerciseStartMs = startedAt ? Date.parse(startedAt) : undefined

  const incidents = useMemo(() => (scenario ? byPriority(scenario.incidents, plan) : []), [scenario, plan])
  const [selectedId, setSelectedId] = useState<string>()
  const selectedIndex = incidents.findIndex((incident) => incident.id === selectedId)
  const selected = selectedIndex >= 0 ? incidents[selectedIndex] : undefined

  const move = (step: number) => {
    if (incidents.length === 0) return
    const next = selectedIndex < 0 ? 0 : Math.min(incidents.length - 1, Math.max(0, selectedIndex + step))
    setSelectedId(incidents[next].id)
    document.getElementById(`incident-${incidents[next].id}`)?.scrollIntoView({ block: 'nearest' })
  }

  useHotkeys({
    j: () => move(1),
    k: () => move(-1),
    Enter: () => {
      if (plan) void navigate({ to: '/plans/$decisionId', params: { decisionId: plan.decision_id } })
    },
  })

  if (status.isError) return <div className="p-6"><Notice tone="high">Cannot reach the API: {status.error.message}</Notice></div>
  if (status.data && !status.data.exercise) {
    return (
      <div className="p-6">
        <h1 className="text-lg font-semibold">No exercise loaded</h1>
        <p className="text-muted">Seed one with <code className="font-mono">python scripts/seed_lucknow_exercise.py</code>.</p>
      </div>
    )
  }

  return (
    <div
      className="grid h-full gap-px bg-divider"
      style={{
        gridTemplateColumns: '340px minmax(0, 1fr) 380px',
        gridTemplateRows: 'minmax(0, 1fr) 152px',
        gridTemplateAreas: '"queue map inspector" "timeline timeline timeline"',
      }}
    >
      <h1 className="sr-only">Operations board{status.data?.exercise ? `: ${status.data.exercise.name}` : ''}</h1>
      <IncidentQueue
        incidents={incidents}
        plan={plan}
        labels={labels}
        selectedId={selectedId}
        onSelect={setSelectedId}
        exerciseStartMs={exerciseStartMs}
        now={now}
      />
      <div className="min-h-0 [grid-area:map]">
        {scenario && mapSlot ? (
          mapSlot({ scenario, plan, labels, selectedId, onSelect: setSelectedId })
        ) : (
          <Panel title="Map" labelledBy="map-title" className="h-full">
            <p className="p-3 text-muted">{scenario ? 'Map not built yet.' : 'Loading exercise…'}</p>
          </Panel>
        )}
      </div>
      {scenario ? (
        <Inspector incident={selected} scenario={scenario} plan={plan} labels={labels} exerciseStartMs={exerciseStartMs} now={now} />
      ) : (
        <Panel title="Inspector" labelledBy="inspector-title" className="[grid-area:inspector]">
          <p className="p-3 text-muted">Loading…</p>
        </Panel>
      )}
      <EventTimeline />
    </div>
  )
}

export interface MapSlotProps {
  scenario: import('../../types').Scenario
  plan: import('../../api/types').StoredDecision | undefined
  labels: import('../../api/types').Labels | undefined
  selectedId: string | undefined
  onSelect: (id: string) => void
}
