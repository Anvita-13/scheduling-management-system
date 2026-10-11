import { useState } from 'react'
import { Link } from 'react-router-dom'
import { adminApi } from '../../api'
import { slotTimes } from './Offerings'
import { Alert, Async, Badge, Button, Card, EmptyState, PageHeader } from '../../components/ui'
import { useApi } from '../../hooks/useApi'

export default function SlotChart() {
  const state = useApi(() => adminApi.slotChart())
  const [kind, setKind] = useState('ALL')
  return (
    <>
      <PageHeader
        title="Slot chart"
        subtitle="Every slot that has offerings, and what sits in it. Different subjects in the same slot are alternatives: a student can take only one of them. Slots that overlap in time (a theory slot and a lab slot, say) clash too."
      />
      <Async state={state}>
        {(d) => {
          const shown = d.slots.filter((s) => kind === 'ALL' || s.kind === kind)
          return (
            <div className="space-y-6">
              <div className="flex flex-wrap items-center gap-3">
                <div className="inline-flex rounded-lg border border-slate-300 bg-white p-1">
                  {[['ALL', 'All'], ['THEORY', 'Theory'], ['LAB', 'Lab']].map(([k, label]) => (
                    <button key={k} onClick={() => setKind(k)} className={`rounded-md px-3 py-1 text-sm font-medium ${kind === k ? 'bg-brand-600 text-white' : 'text-slate-600 hover:bg-slate-100'}`}>{label}</button>
                  ))}
                </div>
                <span className="text-sm text-slate-500">{shown.length} slot(s) in use · {d.free_slots.THEORY} theory and {d.free_slots.LAB} lab slots still free</span>
              </div>

              {d.unscheduled.length > 0 && (
                <Alert kind="warning" title={`${d.unscheduled.length} offering(s) have no slot yet`}>
                  {d.unscheduled.map((u) => `${u.subject_code} (${u.faculty})`).join(', ')}.{' '}
                  <Link to="/admin/scheduling" className="font-semibold underline">Run the optimiser</Link> or pick slots on the{' '}
                  <Link to="/admin/offerings" className="font-semibold underline">Offerings</Link> page.
                </Alert>
              )}

              {shown.length === 0 ? <EmptyState title="Nothing is scheduled yet">Add offerings with slots, or run the optimiser.</EmptyState> : (
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                  {shown.map((s) => {
                    const subjects = new Set(s.offerings.map((o) => o.subject_code))
                    return (
                      <Card key={s.id} title={<span>{s.name} <Badge status={s.kind === 'LAB' ? 'REQUESTED' : 'ENROLLED'}>{s.kind === 'LAB' ? 'Lab' : `${s.credits}-credit theory`}</Badge></span>}>
                        <p className="mb-3 text-xs text-slate-500">{slotTimes(s)}</p>
                        {subjects.size > 1 && <p className="mb-2 rounded bg-amber-50 px-2 py-1 text-xs text-amber-800">{subjects.size} subjects share this slot — students pick one</p>}
                        <ul className="space-y-2">
                          {s.offerings.map((o) => (
                            <li key={`${o.class_id}-${o.component}`} className="rounded-lg border border-slate-200 px-3 py-2 text-sm">
                              <div className="flex items-center justify-between">
                                <b>{o.subject_code}{o.component === 'LAB' ? ' (lab)' : ''}</b>
                                <span className="text-xs text-slate-500">{o.room || 'no room'}</span>
                              </div>
                              <div className="text-xs text-slate-600">{o.faculty} · {o.enrolled}/{o.seats} seats</div>
                            </li>
                          ))}
                        </ul>
                      </Card>
                    )
                  })}
                </div>
              )}
              <div><Button variant="secondary" onClick={state.reset}>Refresh</Button></div>
            </div>
          )
        }}
      </Async>
    </>
  )
}
