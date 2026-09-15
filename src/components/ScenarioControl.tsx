import { Panel } from './Panel'
import { ActionButton } from './buttons'

interface ScenarioControlProps {
  seedText: string
  onSeedTextChange: (value: string) => void
  onGenerate: () => void
  isGenerating: boolean
}

/** Seed input + "generate scenario" action. Isolated from App so the seed
 * validation/submit flow reads as one focused unit. */
export function ScenarioControl({ seedText, onSeedTextChange, onGenerate, isGenerating }: ScenarioControlProps) {
  return (
    <Panel className="mb-5 flex flex-wrap items-center justify-between gap-4">
      <div>
        <p className="eyebrow">Scenario control</p>
        <p className="mt-1 text-sm text-ink-700">Generate reproducible, synthetic incidents on a 0–100 coordinate grid.</p>
      </div>
      <div className="flex items-center gap-2">
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
