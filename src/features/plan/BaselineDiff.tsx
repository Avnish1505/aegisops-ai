import { useBaseline } from '../../api/queries'
import type { Labels, StoredDecision } from '../../api/types'
import { Mono } from '../../components/ui/Panel'

export function BaselineDiff({ plan, labels }: { plan: StoredDecision; labels: Labels | undefined }) {
  const baseline = useBaseline(plan.decision_id)
  if (baseline.isPending) return <p className="p-3 text-sm text-muted">Solving without constraints…</p>
  if (baseline.isError) return <p className="p-3 text-sm text-high">Baseline unavailable: {baseline.error.message}</p>
  const data = baseline.data
  const unit = (id: string) => labels?.units[id] ?? 'Unit'
  const place = (id: string) => labels?.incidents[id] ?? 'Incident'
  if (data.constraints === 0) {
    return <p className="p-3 text-sm text-muted">No constraints, so this plan is the unconstrained solver plan.</p>
  }
  const delta = data.plan_objective - data.objective
  return (
    <div className="space-y-2 p-3 text-sm">
      <p>
        {data.same_as_plan ? 'The constraints did not change any assignment.' : 'Compared with the solver plan without constraints:'}{' '}
        objective <span className="font-mono">{data.plan_objective.toFixed(1)}</span> vs{' '}
        <span className="font-mono">{data.objective.toFixed(1)}</span>
        {delta > 0 && <> (costs <span className="font-mono">{delta.toFixed(1)}</span> more)</>}.
      </p>
      {data.only_in_plan.length > 0 && (
        <div>
          <h4 className="font-medium">Only in this plan</h4>
          <ul>{data.only_in_plan.map((p) => <li key={`${p.incident_id}${p.resource_id}`}>+ {unit(p.resource_id)} <Mono>{p.resource_id}</Mono> → {place(p.incident_id)} <Mono>{p.incident_id}</Mono></li>)}</ul>
        </div>
      )}
      {data.only_in_baseline.length > 0 && (
        <div>
          <h4 className="font-medium">Only without constraints</h4>
          <ul>{data.only_in_baseline.map((p) => <li key={`${p.incident_id}${p.resource_id}`}>− {unit(p.resource_id)} <Mono>{p.resource_id}</Mono> → {place(p.incident_id)} <Mono>{p.incident_id}</Mono></li>)}</ul>
        </div>
      )}
    </div>
  )
}
