import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { useConfirm, useDismiss, useExercise, useMerge, usePlaceSearch, usePlan, useSeverityPreview, useStatus } from '../../api/queries'
import { SIGNALS, type ConfirmedFields, type IntakeReport, type Signal } from '../../api/types'
import { Button, Mono, Notice, Panel } from '../../components/ui/Panel'
import { SeverityGlyph } from '../../components/ui/SeverityGlyph'
import { useIdentity } from '../../lib/auth'
import { INCIDENT_LABEL, RESOURCE_LABEL } from '../../lib/incidents'
import type { IncidentType, ResourceType } from '../../types'

const INPUT = 'w-full rounded border border-control-border bg-bg px-2 py-1 text-sm'

interface Draft {
  incident_type: IncidentType | ''
  place: ConfirmedFields['place'] | null
  people_count: string
  needs: [ResourceType, number][]
  signals: Signal[]
}

function draftFrom(report: IntakeReport): Draft {
  const fields = report.suggested_fields
  return {
    incident_type: fields?.incident_type ?? '',
    place: fields?.place ?? null,
    people_count: fields?.people_count?.toString() ?? '',
    needs: Object.entries(fields?.needs ?? {}) as [ResourceType, number][],
    signals: fields?.signals ?? [],
  }
}

function toFields(draft: Draft): ConfirmedFields | null {
  if (!draft.incident_type || !draft.place) return null
  const people = draft.people_count.trim() === '' ? null : Number(draft.people_count)
  if (people !== null && (!Number.isInteger(people) || people < 0)) return null
  return {
    incident_type: draft.incident_type,
    place: draft.place,
    people_count: people,
    needs: Object.fromEntries(draft.needs.filter(([, n]) => n > 0)),
    signals: draft.signals,
  }
}

function PlacePicker({ value, onChange }: { value: ConfirmedFields['place'] | null; onChange: (place: ConfirmedFields['place']) => void }) {
  const [query, setQuery] = useState('')
  const results = usePlaceSearch(query)
  return (
    <div className="space-y-1">
      <div className="text-sm">
        {value ? (
          <>
            {value.name} <Mono>{value.lat.toFixed(5)}, {value.lon.toFixed(5)}</Mono>
          </>
        ) : (
          <span className="font-semibold text-high">No place: search the gazetteer</span>
        )}
      </div>
      <input
        aria-label="Search places (OpenStreetMap gazetteer)"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Search Lucknow places"
        className={INPUT}
      />
      {results.data && results.data.length > 0 && (
        <ul aria-label="Place results" className="max-h-40 overflow-auto border border-divider">
          {results.data.map((match) => (
            <li key={match.osm}>
              <button
                type="button"
                className="w-full px-2 py-0.5 text-left text-sm hover:bg-raised"
                onClick={() => {
                  onChange({ name: match.name, lat: match.lat, lon: match.lon })
                  setQuery('')
                }}
              >
                {match.name} <span className="text-muted">{match.kind}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export function FieldEditor({ report, onConfirmed }: { report: IntakeReport; onConfirmed: (report: IntakeReport) => void }) {
  const identity = useIdentity()
  const [draft, setDraft] = useState<Draft>(() => draftFrom(report))
  const [dismissReason, setDismissReason] = useState('')
  const confirm = useConfirm()
  const dismiss = useDismiss()
  const merge = useMerge()
  const fields = toFields(draft)
  const preview = useSeverityPreview(fields)
  const readOnly = !identity || identity.role === 'viewer'

  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => setDraft((current) => ({ ...current, [key]: value }))

  return (
    <Panel title="Fields to confirm" labelledBy="editor-title">
      <form
        className="space-y-3 p-3"
        onSubmit={(event) => {
          event.preventDefault()
          if (fields) confirm.mutate({ id: report.id, fields }, { onSuccess: onConfirmed })
        }}
      >
        <fieldset disabled={readOnly} className="space-y-3">
          <label className="block text-sm">
            Incident type
            <select value={draft.incident_type} onChange={(event) => set('incident_type', event.target.value as IncidentType)} className={INPUT}>
              <option value="">Choose…</option>
              {(Object.keys(INCIDENT_LABEL) as IncidentType[]).map((kind) => (
                <option key={kind} value={kind}>{INCIDENT_LABEL[kind]}</option>
              ))}
            </select>
          </label>
          <div className="text-sm">
            <div>Place</div>
            <PlacePicker value={draft.place} onChange={(place) => set('place', place)} />
          </div>
          <label className="block text-sm">
            People affected
            <input inputMode="numeric" value={draft.people_count} onChange={(event) => set('people_count', event.target.value)} className={INPUT} />
          </label>
          <div className="text-sm">
            <div>Needs <span className="text-muted">(empty: the type's standard needs)</span></div>
            {draft.needs.map(([type, count], index) => (
              <div key={index} className="mt-1 flex gap-2">
                <select
                  aria-label="Resource type"
                  value={type}
                  onChange={(event) => set('needs', draft.needs.map((need, i) => (i === index ? [event.target.value as ResourceType, need[1]] : need)))}
                  className={INPUT}
                >
                  {(Object.keys(RESOURCE_LABEL) as ResourceType[]).map((kind) => (
                    <option key={kind} value={kind}>{RESOURCE_LABEL[kind]}</option>
                  ))}
                </select>
                <input
                  aria-label="Quantity"
                  inputMode="numeric"
                  value={count}
                  onChange={(event) => set('needs', draft.needs.map((need, i) => (i === index ? [need[0], Number(event.target.value) || 0] : need)))}
                  className={`${INPUT} w-16`}
                />
                <Button onClick={() => set('needs', draft.needs.filter((_, i) => i !== index))}>Remove</Button>
              </div>
            ))}
            <Button className="mt-1" onClick={() => set('needs', [...draft.needs, ['ambulance', 1]])}>Add need</Button>
          </div>
          <fieldset className="text-sm">
            <legend>Signals</legend>
            <div className="grid grid-cols-2 gap-x-3">
              {SIGNALS.map((signal) => (
                <label key={signal} className="flex items-center gap-1.5">
                  <input
                    type="checkbox"
                    checked={draft.signals.includes(signal)}
                    onChange={(event) =>
                      set('signals', event.target.checked ? [...draft.signals, signal] : draft.signals.filter((s) => s !== signal))
                    }
                  />
                  {signal.replace('_', ' ')}
                </label>
              ))}
            </div>
          </fieldset>
        </fieldset>
        <div className="border-t border-divider pt-2 text-sm">
          {preview.data ? (
            <div className="flex items-center gap-2">
              Severity by rule: <SeverityGlyph severity={preview.data.severity} /> <span className="text-muted">{preview.data.rule}</span>
            </div>
          ) : (
            <span className="text-muted">Choose a type and a place to see the severity the rules give.</span>
          )}
        </div>
        {!readOnly && (
          <div className="space-y-2">
            <Button type="submit" disabled={!fields || confirm.isPending}>
              {confirm.isPending ? 'Confirming…' : 'Confirm and add to exercise'}
            </Button>
            {confirm.isError && <Notice tone="high">{confirm.error.message}</Notice>}
            {report.duplicates.map((duplicate) => (
              <div key={duplicate.id} className="flex items-center gap-2 text-sm">
                <span className="text-muted">Same as #{duplicate.id}? ({duplicate.rule})</span>
                <Button onClick={() => merge.mutate({ id: report.id, into: duplicate.id })} disabled={merge.isPending}>
                  Merge into #{duplicate.id}
                </Button>
              </div>
            ))}
            <div className="flex gap-2">
              <input aria-label="Reason to dismiss" value={dismissReason} onChange={(event) => setDismissReason(event.target.value)} placeholder="Reason to dismiss" className={INPUT} />
              <Button onClick={() => dismiss.mutate({ id: report.id, reason: dismissReason })} disabled={!dismissReason.trim() || dismiss.isPending}>
                Dismiss
              </Button>
            </div>
            {(merge.isError || dismiss.isError) && <Notice tone="high">{(merge.error ?? dismiss.error)?.message}</Notice>}
          </div>
        )}
      </form>
    </Panel>
  )
}

/** Shown after a confirmation, until another report is selected: the next step is planning. */
export function ConfirmedPanel({ report }: { report: IntakeReport }) {
  const navigate = useNavigate()
  const plan = usePlan()
  const exerciseId = useStatus().data?.exercise?.id
  const exercise = useExercise(exerciseId)
  return (
    <Panel title={`Report #${report.id} confirmed`} labelledBy="confirmed-title">
      <div className="space-y-2 p-3 text-sm">
        <p>{report.text}</p>
        <p>
          Added to the exercise as <Mono>{report.incident_id}</Mono>
          {report.edited_fields?.length ? <> (you edited: {report.edited_fields.join(', ')})</> : ' (model reading accepted as is)'}.
        </p>
        <Button
          disabled={!exercise.data || plan.isPending}
          onClick={() =>
            exercise.data &&
            plan.mutate(
              { scenario: exercise.data },
              { onSuccess: (decision) => void navigate({ to: '/plans/$decisionId', params: { decisionId: decision.decision_id } }) },
            )
          }
        >
          {plan.isPending ? 'Planning…' : 'Plan the exercise now'}
        </Button>
        {plan.isError && <Notice tone="high">{plan.error.message}</Notice>}
      </div>
    </Panel>
  )
}
