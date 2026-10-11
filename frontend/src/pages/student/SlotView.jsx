import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { studentApi } from '../../api'
import { Alert, Async, Badge, Card, EmptyState, Input, PageHeader } from '../../components/ui'
import { useApi } from '../../hooks/useApi'

const ROLE_BADGE = { MANDATORY: ['ENROLLED', 'Mandatory'], GROUP: ['SELECTED', 'Your group'] }

/** All offerings grouped by theory slot: subjects in the same slot are alternatives - you can take only one. */
export default function SlotView() {
  const state = useApi(() => studentApi.offerings())
  const [groupOnly, setGroupOnly] = useState(true)
  const [hideClash, setHideClash] = useState(false)
  const [q, setQ] = useState('')

  const grouped = useMemo(() => {
    const rows = (state.data || []).filter((o) =>
      (!groupOnly || o.group_role) && (!hideClash || o.clash_with.length === 0) &&
      `${o.subject_code} ${o.subject_name} ${o.faculty_name}`.toLowerCase().includes(q.toLowerCase()))
    const by = {}
    rows.forEach((o) => { (by[o.theory_slot] ||= { slot: o.theory_slot, times: o.theory_times, items: [] }).items.push(o) })
    return Object.values(by).sort((a, b) => a.slot.localeCompare(b.slot))
  }, [state.data, groupOnly, hideClash, q])

  return (
    <>
      <PageHeader title="Slot view" subtitle="Every offering by its theory slot. Subjects that share a slot are alternatives: you can hold only one of them. Offerings that overlap in time with something you already hold are marked and cannot be requested." />
      <div className="mb-4 flex flex-wrap items-center gap-4 text-sm">
        <label className="flex items-center gap-2"><input type="checkbox" className="accent-brand-600" checked={groupOnly} onChange={(e) => setGroupOnly(e.target.checked)} /> Only my group's subjects</label>
        <label className="flex items-center gap-2"><input type="checkbox" className="accent-brand-600" checked={hideClash} onChange={(e) => setHideClash(e.target.checked)} /> Hide options that clash with mine</label>
        <div className="w-64"><Input placeholder="Search subject or faculty…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search" /></div>
      </div>
      <Async state={state}>
        {() => grouped.length === 0 ? <EmptyState title="Nothing to show">Try unticking the filters, or ask the administration to schedule the offerings.</EmptyState> : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {grouped.map((g) => (
              <Card key={g.slot} title={g.slot} actions={<span className="text-xs text-slate-500">{new Set(g.items.map((i) => i.subject_code)).size > 1 ? 'alternatives — pick one' : ''}</span>}>
                <p className="mb-2 text-xs text-slate-500">{g.times}</p>
                <ul className="space-y-2">
                  {g.items.map((o) => (
                    <li key={o.class_id} className={`rounded-lg border px-3 py-2 text-sm ${o.mine ? 'border-emerald-300 bg-emerald-50' : o.clash_with.length ? 'border-rose-200 bg-rose-50/50' : 'border-slate-200'}`}>
                      <div className="flex flex-wrap items-center justify-between gap-1">
                        <b>{o.subject_code}</b>
                        <span className="flex gap-1">
                          {o.group_role && <Badge status={ROLE_BADGE[o.group_role][0]}>{ROLE_BADGE[o.group_role][1]}</Badge>}
                          {o.mine && <Badge status="ENROLLED">{o.my_status === 'ENROLLED' ? 'Enrolled' : 'Requested'}</Badge>}
                        </span>
                      </div>
                      <div className="text-xs text-slate-600">{o.subject_name}</div>
                      <div className="text-xs text-slate-600">{o.faculty_name}{o.has_lab && o.lab_slot ? ` · lab ${o.lab_slot}` : ''}</div>
                      <div className="text-xs text-slate-500">{o.remaining} of {o.capacity} seats free · {o.status}</div>
                      {o.clash_with.length > 0 && <div className="text-xs font-medium text-rose-600">Clashes with {o.clash_with.join(', ')}</div>}
                      {!o.mine && o.my_status !== 'ENROLLED' && o.clash_with.length === 0 && <Link className="text-xs font-medium text-brand-700 underline" to={`/student/subjects/${o.subject_id}`}>Open subject</Link>}
                    </li>
                  ))}
                </ul>
              </Card>
            ))}
          </div>
        )}
      </Async>
      <div className="mt-4"><Alert kind="info">Open a subject from the <Link className="font-semibold underline" to="/student/subjects">Subjects</Link> page (select it first) to request one of its faculty options.</Alert></div>
    </>
  )
}
