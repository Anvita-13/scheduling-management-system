import { useEffect, useMemo, useState } from 'react'
import { adminApi } from '../../api'
import CapacityEditor from '../../components/CapacityEditor'
import { Alert, Async, Badge, Button, Card, EmptyState, Field, Input, Modal, PageHeader, Select } from '../../components/ui'
import { useToast } from '../../components/Toast'
import { useAction, useApi } from '../../hooks/useApi'

export const slotTimes = (slot) => slot.periods.map((p) => `${p.day} ${p.start_time}`).join(', ')
const slotLabel = (s) => `${s.name} — ${slotTimes(s)}${s.used_by ? `  (${s.used_by} offering${s.used_by > 1 ? 's' : ''})` : ''}`

function SlotPickers({ subject, slots, theory, lab, onTheory, onLab, optionalLabel }) {
  const theorySlots = slots.filter((s) => s.kind === 'THEORY' && s.credits === subject.credits)
  const labSlots = slots.filter((s) => s.kind === 'LAB')
  return (
    <>
      <div className="min-w-[260px] flex-1">
        <Field label={`Theory slot (${subject.credits}-credit)`}>
          <Select value={theory} onChange={(e) => onTheory(e.target.value)}>
            <option value="">{optionalLabel}</option>
            {theorySlots.map((s) => <option key={s.id} value={s.id}>{slotLabel(s)}</option>)}
          </Select>
        </Field>
      </div>
      {subject.has_lab && (
        <div className="min-w-[260px] flex-1">
          <Field label="Lab slot (this faculty's own lab)">
            <Select value={lab} onChange={(e) => onLab(e.target.value)}>
              <option value="">{optionalLabel}</option>
              {labSlots.map((s) => <option key={s.id} value={s.id}>{slotLabel(s)}</option>)}
            </Select>
          </Field>
        </div>
      )}
    </>
  )
}

function AddOffering({ subject, slots, onDone }) {
  const toast = useToast()
  const { busy, run } = useAction(toast)
  const [theory, setTheory] = useState('')
  const [lab, setLab] = useState('')
  const [facultyId, setFacultyId] = useState('')
  const [capacity, setCapacity] = useState(30)
  const [faculty, setFaculty] = useState({ available: [], unavailable: [] })
  const [showWhy, setShowWhy] = useState(false)

  // The list of teachers always reflects the chosen slot(s): anyone already teaching at an overlapping time is removed.
  useEffect(() => {
    const complete = !theory || !subject.has_lab || lab
    if (!complete) { setFaculty({ available: [], unavailable: [] }); return }
    let alive = true
    adminApi.eligibleFaculty({ subject_id: subject.id, theory_slot_id: theory || null, lab_slot_id: lab || null })
      .then((r) => { if (alive) { setFaculty(r); if (!r.available.some((f) => String(f.faculty_id) === facultyId)) setFacultyId('') } })
      .catch((e) => toast.error(e.message))
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subject.id, subject.offerings.length, theory, lab])

  const placing = Boolean(theory)
  const ready = facultyId && (!placing || !subject.has_lab || lab)
  return (
    <form
      className="mt-4 rounded-lg bg-slate-50 p-4"
      onSubmit={(e) => {
        e.preventDefault()
        run(
          () => adminApi.createOffering({
            subject_id: subject.id, faculty_id: Number(facultyId), capacity: Number(capacity),
            theory_slot_id: theory ? Number(theory) : null, lab_slot_id: lab ? Number(lab) : null,
          }),
          {
            success: (r) => (r.warnings?.length ? `Offering added. Note: ${r.warnings[0]}` : 'Offering added'),
            onDone: () => { setTheory(''); setLab(''); setFacultyId(''); return onDone() },
          },
        )
      }}
    >
      <p className="mb-3 text-sm font-semibold text-slate-700">Add a faculty option for {subject.code}</p>
      <div className="flex flex-wrap items-end gap-3">
        <SlotPickers subject={subject} slots={slots} theory={theory} lab={lab} onTheory={setTheory} onLab={setLab}
          optionalLabel="Leave for the optimiser" />
        <div className="min-w-[220px]">
          <Field label="Faculty" hint={placing ? 'Only teachers free in these slots are listed' : 'Pick slots first to filter by availability'}>
            <Select required value={facultyId} onChange={(e) => setFacultyId(e.target.value)}>
              <option value="">Select…</option>
              {faculty.available.map((f) => <option key={f.faculty_id} value={f.faculty_id}>{f.name} · {f.courses} course(s)</option>)}
            </Select>
          </Field>
        </div>
        <div className="w-24"><Field label="Seats"><Input type="number" min="0" max="1000" value={capacity} onChange={(e) => setCapacity(e.target.value)} /></Field></div>
        <Button type="submit" busy={busy} disabled={!ready}>Add</Button>
      </div>
      {faculty.unavailable.length > 0 && (
        <div className="mt-2 text-xs text-slate-500">
          <button type="button" className="underline" onClick={() => setShowWhy(!showWhy)}>
            {faculty.unavailable.length} teacher(s) not listed — why?
          </button>
          {showWhy && (
            <ul className="mt-1 list-disc pl-5">
              {faculty.unavailable.map((f) => <li key={f.faculty_id}>{f.name}: {f.reason}</li>)}
            </ul>
          )}
        </div>
      )}
    </form>
  )
}

function ChangeSlots({ subject, offering, slots, onClose, onDone }) {
  const toast = useToast()
  const { busy, run } = useAction(toast)
  const [theory, setTheory] = useState(offering.theory_slot_id ? String(offering.theory_slot_id) : '')
  const [lab, setLab] = useState(offering.lab_slot_id ? String(offering.lab_slot_id) : '')
  return (
    <Modal title={`Slots for ${subject.code} — ${offering.faculty_name}`} onClose={onClose}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          run(() => adminApi.placeOffering(offering.id, { theory_slot_id: theory ? Number(theory) : null, lab_slot_id: lab ? Number(lab) : null }), {
            success: (r) => (r.warnings?.length ? `Saved. Note: ${r.warnings[0]}` : 'Slots saved'),
            onDone: async () => { await onDone(); onClose() },
          })
        }}
      >
        <SlotPickers subject={subject} slots={slots} theory={theory} lab={lab} onTheory={setTheory} onLab={setLab} optionalLabel="No slot (un-place)" />
        <p className="text-xs text-slate-500">The server refuses a slot that overlaps this teacher's other classes. Rooms are assigned automatically.</p>
        <Button type="submit" busy={busy}>Save</Button>
      </form>
    </Modal>
  )
}

function SubjectCard({ subject, slots, onChanged }) {
  const toast = useToast()
  const { busy, run } = useAction(toast)
  const [editing, setEditing] = useState(null)
  return (
    <Card
      title={<span>{subject.code} — {subject.name} <span className="ml-2 text-sm font-normal text-slate-500">{subject.credits}{subject.has_lab ? `+${subject.lab_credits} (theory+lab)` : ' (theory only)'} credits</span></span>}
      actions={<>
        {subject.groups.map((g) => <Badge key={g} status={g.includes('mandatory') ? 'ENROLLED' : 'SELECTED'}>{g}</Badge>)}
        <Button size="sm" variant="secondary" busy={busy} disabled={subject.offerings.length > 0}
          onClick={() => window.confirm(`Delete ${subject.code}?`) && run(() => adminApi.deleteSubject(subject.id), { success: 'Subject deleted', onDone: onChanged })}>Delete</Button>
      </>}
    >
      {subject.offerings.length === 0 ? <EmptyState title="No faculty options yet" /> : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead><tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
              <th className="px-2 py-2">Faculty</th><th className="px-2 py-2">Theory slot</th>{subject.has_lab && <th className="px-2 py-2">Lab slot</th>}
              <th className="px-2 py-2">Room{subject.has_lab ? 's' : ''}</th><th className="px-2 py-2">Seats</th><th className="px-2 py-2">Status</th><th />
            </tr></thead>
            <tbody className="divide-y divide-slate-100">
              {subject.offerings.map((o) => (
                <tr key={o.id}>
                  <td className="px-2 py-2 font-medium">{o.faculty_name}</td>
                  <td className="px-2 py-2">{o.theory_slot ? <><b>{o.theory_slot}</b><div className="text-xs text-slate-500">{o.theory_times}</div></> : <Badge status="PENDING">Needs slot</Badge>}</td>
                  {subject.has_lab && <td className="px-2 py-2">{o.lab_slot ? <><b>{o.lab_slot}</b><div className="text-xs text-slate-500">{o.lab_times}</div></> : <span className="text-slate-400">—</span>}</td>}
                  <td className="px-2 py-2 text-xs">{o.scheduled ? <>{o.room || <span className="text-rose-600">no room</span>}{subject.has_lab && <> / {o.lab_room || <span className="text-rose-600">no lab</span>}</>}</> : '—'}</td>
                  <td className="px-2 py-2"><CapacityEditor key={`${o.id}-${o.capacity}`} cls={o} onChanged={onChanged} /></td>
                  <td className="px-2 py-2"><Badge status={o.status} />{o.pending_requests > 0 && <span className="ml-1 text-xs text-slate-500">{o.pending_requests} waiting</span>}</td>
                  <td className="whitespace-nowrap px-2 py-2 text-right">
                    <Button size="sm" variant="secondary" disabled={o.locked} title={o.locked ? 'Students are enrolled or waiting' : ''} onClick={() => setEditing(o)}>Slots</Button>{' '}
                    {o.status === 'OPEN'
                      ? <Button size="sm" variant="secondary" busy={busy} onClick={() => window.confirm('Close this class? Waiting students are rejected and notified.') && run(() => adminApi.closeClass(o.id), { success: 'Class closed', onDone: onChanged })}>Close</Button>
                      : <Button size="sm" variant="secondary" busy={busy} disabled={o.remaining === 0} onClick={() => run(() => adminApi.reopenClass(o.id), { success: 'Class reopened', onDone: onChanged })}>Reopen</Button>}{' '}
                    <Button size="sm" variant="ghost" busy={busy} disabled={o.locked} onClick={() => window.confirm('Remove this offering?') && run(() => adminApi.deleteOffering(o.id), { success: 'Offering removed', onDone: onChanged })}>Remove</Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <AddOffering subject={subject} slots={slots} onDone={onChanged} />
      {editing && <ChangeSlots subject={subject} offering={editing} slots={slots} onClose={() => setEditing(null)} onDone={onChanged} />}
    </Card>
  )
}

function NewSubject({ onCreated }) {
  const toast = useToast()
  const { busy, run } = useAction(toast)
  const [f, setF] = useState({ code: '', name: '', credits: 3, lab_credits: 0 })
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  return (
    <Card title="Add a subject">
      <form className="grid gap-4 md:grid-cols-5" onSubmit={async (e) => {
        e.preventDefault()
        const res = await run(() => adminApi.createSubject({ ...f, credits: Number(f.credits), lab_credits: Number(f.lab_credits) }), { success: 'Subject created', onDone: onCreated })
        if (res) setF({ code: '', name: '', credits: 3, lab_credits: 0 })
      }}>
        <Field label="Code"><Input required value={f.code} onChange={set('code')} placeholder="BCSE202L" /></Field>
        <Field label="Name"><Input required value={f.name} onChange={set('name')} placeholder="Data Structures" /></Field>
        <Field label="Theory credits" hint="2, 3 or 4 (matches slot packages)"><Input required type="number" min="1" max="6" value={f.credits} onChange={set('credits')} /></Field>
        <Field label="Lab credits" hint="0 = theory only"><Input required type="number" min="0" max="4" value={f.lab_credits} onChange={set('lab_credits')} /></Field>
        <div className="flex items-end"><Button type="submit" busy={busy} className="w-full">Add subject</Button></div>
      </form>
    </Card>
  )
}

export default function Offerings() {
  const toast = useToast()
  const { busy, run } = useAction(toast)
  const state = useApi(async () => {
    const [subjects, slots] = await Promise.all([adminApi.subjects(), adminApi.slots()])
    return { subjects, slots }
  })
  const [query, setQuery] = useState('')
  const filtered = useMemo(
    () => (state.data?.subjects || []).filter((s) => `${s.code} ${s.name}`.toLowerCase().includes(query.toLowerCase())),
    [state.data, query],
  )
  return (
    <>
      <PageHeader
        title="Offerings & slots"
        subtitle="Each offering is one faculty member teaching one subject in its own slot(s). For theory+lab courses the theory slot and that faculty's lab slot are chosen together and students pick them as one unit."
      />
      <div className="space-y-6">
        <NewSubject onCreated={state.reload} />
        <Async state={state}>
          {({ subjects, slots }) => (
            <>
              {slots.length === 0 && (
                <Alert kind="warning" title="No slot chart yet">
                  Slots are the weekly time packages offerings sit in (A1+TA1, L1+L2, …).
                  <div className="mt-2"><Button size="sm" busy={busy} onClick={() => run(() => adminApi.loadStandardSlots(), { success: (r) => `${r.created} slots created`, onDone: state.reload })}>Load the standard slot chart</Button></div>
                </Alert>
              )}
              {subjects.length === 0 ? <EmptyState title="No subjects yet">Add your first subject above.</EmptyState> : (
                <>
                  <div className="max-w-sm"><Input placeholder="Filter subjects…" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Filter subjects" /></div>
                  {filtered.map((s) => <SubjectCard key={s.id} subject={s} slots={slots} onChanged={state.reload} />)}
                </>
              )}
            </>
          )}
        </Async>
      </div>
    </>
  )
}
