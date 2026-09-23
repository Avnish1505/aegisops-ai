import type { ExerciseSummary } from '../types'
import { Panel } from './Panel'
import { ActionButton, SecondaryButton } from './buttons'

interface ScenarioControlProps {
  seedText: string
  onSeedTextChange: (value: string) => void
  onGenerate: () => void
  isGenerating: boolean
  exercises: ExerciseSummary[]
  onLoadExercise: (exerciseId: string) => void
}

/** Seed input + "generate scenario" action. Isolated from App so the seed
 * validation/submit flow reads as one focused unit. */
export function ScenarioControl({ seedText, onSeedTextChange, onGenerate, isGenerating, exercises, onLoadExercise }: ScenarioControlProps) {
  return (
    <Panel className="mb-5 flex flex-wrap items-center justify-between gap-4">
      <div>
        <p className="eyebrow">Scenario control</p>
        <p className="mt-1 text-sm text-ink-700">Load a saved exercise, or generate reproducible synthetic incidents in Lucknow.</p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {exercises.map((exercise) => (
          <SecondaryButton key={exercise.id} onClick={() => onLoadExercise(exercise.id)} title={exercise.description}>
            {exercise.name} ({exercise.incidents} incidents)
          </SecondaryButton>
        ))}
        <label className="sr-only" htmlFor="seed">Scenario seed</label>
        <input
          id="seed"
          value={seedText}
          onChange={(event) => onSeedTextChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') onGenerate()
          }}
          inputMode="numeric"
          placeholder="Random seed"
          className="w-32 border border-ink-300 bg-paper-sunken px-3 py-2 text-sm font-mono text-ink-800 placeholder:text-ink-400"
        />
        <ActionButton onClick={onGenerate} loading={isGenerating}>
          {isGenerating ? 'Generating…' : 'Generate scenario'}
        </ActionButton>
      </div>
    </Panel>
  )
}
