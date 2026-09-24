import { Link, useNavigate } from '@tanstack/react-router'
import { usePlan } from '../../api/queries'
import type { Labels, StoredDecision } from '../../api/types'
import { Button, Mono, Notice, Panel } from '../../components/ui/Panel'
import { SeverityGlyph } from '../../components/ui/SeverityGlyph'
import { useIdentity } from '../../lib/auth'
import { INCIDENT_LABEL, RESOURCE_LABEL, incidentState, latestReportMin, minutes, nearestCapableUnits, reportedAtMs } from '../../lib/incidents'
import { age } from '../../lib/time'
import type { Incident, ResourceType, Scenario } from '../../types'

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-3 py-0.5">
      <dt className="w-28 shrink-0 text-muted">{label}</dt>
      <dd>{children}</dd>
    </div>
  )
}

function UnitRow({ name, id, eta }: { name: string; id: string; eta: string }) {
  return (
    <li className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 py-0.5">
      <span className="truncate">{name}</span>
      <span className="row-span-2 self-center font-mono">{eta}</span>
      <Mono className="truncate">{id}</Mono>
    </li>
  )
}

export function Inspector({
  incident,
  scenario,
  plan,
  labels,
  exerciseStartMs,
  now,
}: {
  incident: Incident | undefined
  scenario: Scenario
  plan: StoredDecision | undefined
  labels: Labels | undefined
  exerciseStartMs: number | undefined
  now: number
}) {
  const identity = useIdentity()
  const navigate = useNavigate()
  const planning = usePlan()
  const canPlan = identity?.role === 'operator' || identity?.role === 'approver' || identity?.role === 'admin'

  const planButton = canPlan && (
    <Button
      disabled={planning.isPending}
      onClick={() =>
        planning.mutate(
          { scenario },
          { onSuccess: (decision) => void navigate({ to: '/plans/$decisionId', params: { decisionId: decision.decision_id } }) },
        )
      }
    >
      {planning.isPending ? 'Planning…' : plan ? 'Re-plan exercise' : 'Plan exercise'}
    </Button>
  )

  if (!incident) {
    return (
      <Panel title="Inspector" labelledBy="inspector-title" className="[grid-area:inspector]" actions={planButton}>
        <p className="p-3 text-muted">Select an incident (J / K, then Enter to open its plan).</p>
      </Panel>
    )
  }

  const latestMin = latestReportMin(scenario.incidents)
  const state = incidentState(incident, plan)
  const options = nearestCapableUnits(incident, scenario, plan?.travel_times)
  const unitName = (id: string) => labels?.units[id] ?? 'Unit'
  const provider = plan?.travel_times.provider
  const degraded = plan?.travel_times.degraded

  return (
    <Panel title="Inspector" labelledBy="inspector-title" className="[grid-area:inspector]" actions={planButton}>
      <div className="space-y-3 p-3">
        <header>
          <h3 className="text-lg font-semibold">{labels?.incidents[incident.id] ?? 'Unnamed location'}</h3>
          <div className="flex items-center gap-3">
            <Mono>{incident.id}</Mono>
            <SeverityGlyph severity={incident.severity} />
            <span className="font-mono text-sm text-muted">
              {exerciseStartMs !== undefined ? `${age(reportedAtMs(incident, exerciseStartMs, latestMin), now)} ago` : `T+${incident.reported_at_min} min`}
            </span>
          </div>
        </header>

        {planning.isError && <Notice tone="high">Could not plan: {planning.error.message}</Notice>}

        <section aria-label="Source report">
          <h4 className="mb-1 text-sm font-semibold uppercase tracking-wide text-muted">Source report</h4>
          {incident.report ? (
            <blockquote className="border-l-2 border-divider pl-3">{incident.report}</blockquote>
          ) : (
            <p className="text-muted">No report text.</p>
          )}
        </section>

        <section aria-label="Fields">
          <h4 className="mb-1 text-sm font-semibold uppercase tracking-wide text-muted">Fields</h4>
          <dl className="text-sm">
            <Field label="Type">{INCIDENT_LABEL[incident.type]}</Field>
            <Field label="People">{incident.people_affected}</Field>
            <Field label="Needs">
              {Object.entries(incident.resources_needed)
                .map(([type, count]) => `${count} ${RESOURCE_LABEL[type as ResourceType]}`)
                .join(', ')}
            </Field>
            <Field label="Location">
              <Mono>
                {incident.location.lat.toFixed(5)}, {incident.location.lon.toFixed(5)}
              </Mono>
            </Field>
          </dl>
        </section>

        <section aria-label="Nearest capable units">
          <h4 className="mb-1 text-sm font-semibold uppercase tracking-wide text-muted">
            Nearest capable units {provider && <span className="normal-case">· ETA from {provider}</span>}
          </h4>
          {degraded && <Notice tone="high">Road times unavailable: these are straight-line estimates.</Notice>}
          {!plan && <p className="text-muted">Plan the exercise to compute road travel times.</p>}
          {plan &&
            Object.entries(options).map(([type, list]) => (
              <div key={type} className="mb-1">
                <div className="text-sm text-muted">{RESOURCE_LABEL[type as ResourceType]}</div>
                {list.length === 0 && <div className="text-sm font-semibold text-high">None available</div>}
                <ul className="text-sm">
                  {list.map(({ unit, minutes: eta }) => (
                    <UnitRow key={unit.id} name={unitName(unit.id)} id={unit.id} eta={minutes(eta)} />
                  ))}
                </ul>
              </div>
            ))}
        </section>

        {plan && (
          <section aria-label="Current plan">
            <h4 className="mb-1 text-sm font-semibold uppercase tracking-wide text-muted">In plan {plan.decision_id}</h4>
            <ul className="text-sm">
              {state.assigned.map((assignment) => (
                <UnitRow
                  key={assignment.resource_id}
                  name={unitName(assignment.resource_id)}
                  id={assignment.resource_id}
                  eta={`ETA ${minutes(plan.travel_times.minutes[assignment.resource_id]?.[incident.id] ?? assignment.travel_minutes)}`}
                />
              ))}
              {state.unmet.map((unmet) => (
                <li key={unmet.resource_type} className={`font-semibold ${unmet.severity === 'critical' ? 'text-critical' : 'text-high'}`}>
                  Unmet: {unmet.quantity} {RESOURCE_LABEL[unmet.resource_type]}
                </li>
              ))}
            </ul>
            <Link to="/plans/$decisionId" params={{ decisionId: plan.decision_id }} className="mt-2 inline-block underline">
              Open plan {plan.decision_id} (Enter)
            </Link>
          </section>
        )}
      </div>
    </Panel>
  )
}
