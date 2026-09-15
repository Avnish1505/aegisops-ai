import { useState } from 'react'
import { fetchDecision, fetchScenario } from './api'
import type { Assignment, Decision, Scenario, SelectedEntity } from './types'
import { AppShell } from './components/AppShell'
import { ScenarioControl } from './components/ScenarioControl'
import { ErrorBanner } from './components/ErrorBanner'
import { EmptyState } from './components/EmptyState'
import { Grid } from './components/Grid'
import { DetailPanel } from './components/DetailPanel'
import { ResultsPanel } from './components/ResultsPanel'
import { SituationOverview } from './components/SituationOverview'
import { StatusIndicator } from './components/StatusIndicator'
import { Panel } from './components/Panel'
import { ActionButton } from './components/buttons'

function App() {
  const [seedText, setSeedText] = useState('42')
  const [scenario, setScenario] = useState<Scenario | null>(null)
  const [decision, setDecision] = useState<Decision | null>(null)
  const [selected, setSelected] = useState<SelectedEntity>(null)
  const [activeAssignment, setActiveAssignment] = useState<Assignment | null>(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const [isRecommending, setIsRecommending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const generateScenario = async () => {
    const normalized = seedText.trim()
    const seed = normalized === '' ? undefined : Number(normalized)
    if (seed !== undefined && (!Number.isSafeInteger(seed) || seed < 0)) {
      setError('Seed must be a whole non-negative number, or leave it blank for a random synthetic scenario.')
      return
    }
    setIsGenerating(true)
    setError(null)
    try {
      const next = await fetchScenario(seed)
      setScenario(next)
      setDecision(null)
      setSelected(null)
      setActiveAssignment(null)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not generate a scenario.')
    } finally {
      setIsGenerating(false)
    }
  }

  const getRecommendation = async () => {
    if (!scenario) return
    setIsRecommending(true)
    setError(null)
    setActiveAssignment(null)
    setDecision(null)
    try {
      setDecision(await fetchDecision(scenario))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not retrieve a recommendation.')
    } finally {
      setIsRecommending(false)
    }
  }

  return (
    <AppShell
      statusLine={
        <StatusIndicator>
          Research environment <span className="mx-1 text-ink-300">/</span> No automated dispatch
        </StatusIndicator>
      }
    >
      <ScenarioControl
        seedText={seedText}
        onSeedTextChange={setSeedText}
        onGenerate={() => void generateScenario()}
        isGenerating={isGenerating}
      />

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      {!scenario ? (
        <EmptyState
          eyebrow="Awaiting synthetic scenario"
          title="Start with seed 42"
          titleTag="h2"
          description="Generate a scenario to inspect incidents, available capabilities, and an operator-gated allocation advisory."
          className="min-h-[500px]"
        />
      ) : (
        <>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="eyebrow">Active scenario</p>
              <p className="mt-1 font-mono text-sm text-accent-700">{scenario.scenario_id}</p>
            </div>
            <ActionButton onClick={() => void getRecommendation()} loading={isRecommending}>
              {isRecommending ? 'Analyzing scenario…' : 'Get recommendation'}
            </ActionButton>
          </div>

          <SituationOverview scenario={scenario} decision={decision} />

          <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_330px]">
            <Panel>
              <div className="mb-3 flex items-center justify-between">
                <div>
                  <h2 className="panel-heading">Operational coordinate plane</h2>
                  <p className="mt-0.5 text-xs text-ink-500">Synthetic grid only — not geographic location data.</p>
                </div>
                <span className="font-mono text-[10px] text-ink-500">X 0–100 / Y 0–100</span>
              </div>
              <Grid
                scenario={scenario}
                decision={decision}
                selected={selected}
                activeAssignment={activeAssignment}
                onSelect={setSelected}
              />
            </Panel>
            <Panel as="aside" className="self-start">
              <p className="eyebrow">Marker inspection</p>
              <h2 className="mt-1 mb-4 panel-heading">Entity details</h2>
              <DetailPanel selected={selected} decision={decision} />
            </Panel>
          </div>

          {isRecommending && (
            <div className="mt-5 border border-accent-700/25 bg-accent-100/40 p-4 text-sm text-ink-700">
              <span className="mr-2 inline-block h-2 w-2 animate-pulse rounded-full bg-accent-700" />
              Requesting advisory from the rule-based baseline engine. No action is being taken.
            </div>
          )}

          {decision && (
            <div className="mt-5">
              <ResultsPanel decision={decision} onActiveAssignment={setActiveAssignment} />
            </div>
          )}
        </>
      )}
    </AppShell>
  )
}

export default App
