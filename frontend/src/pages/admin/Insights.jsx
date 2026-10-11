import { useState } from 'react'
import { adminApi } from '../../api'
import { Alert, Async, Badge, Button, Card, EmptyState, Field, PageHeader, Select, StatCard, Table } from '../../components/ui'
import { useToast } from '../../components/Toast'
import { useApi } from '../../hooks/useApi'
import { formatDateTime } from '../../utils/format'

const TABS = [
  ['fifo', '1 · FIFO Queue'],
  ['greedy', '2 · Greedy Faculty Allocation'],
  ['coloring', '3 · Backtracking Graph Coloring'],
  ['flow', '4 · Edmonds-Karp Max Flow'],
]

const WHERE = {
  fifo: 'Used by: every class\'s pending join-request queue (student request → faculty accepts from the front).',
  greedy: 'Used by: suggesting / auto-placing a student with another faculty when the chosen class is full.',
  coloring: 'Used by: the slot optimiser on the Scheduling page (class parts = vertices, "must not overlap" = edges, slot packages = colours).',
  flow: 'Used by: Admin capacity planning — how many students could be seated, and which classes are bottlenecks.',
}

function Complexity({ data }) {
  return (
    <div className="rounded-lg bg-slate-100 px-4 py-3 text-sm text-slate-700">
      <p className="mb-1 font-semibold">Complexity</p>
      <ul className="space-y-0.5">{Object.entries(data).map(([k, v]) => <li key={k}><span className="font-mono text-xs text-slate-500">{k.replaceAll('_', ' ')}:</span> {v}</li>)}</ul>
    </div>
  )
}

function useRunner(fn) {
  const toast = useToast()
  const [state, setState] = useState({ data: null, loading: false, error: null })
  const run = async () => {
    setState({ data: null, loading: true, error: null })
    try { setState({ data: await fn(), loading: false, error: null }) }
    catch (e) { setState({ data: null, loading: false, error: e }); toast.error(e.message) }
  }
  return [state, run]
}

function Result({ state, children }) {
  if (state.loading) return <p className="text-sm text-slate-500">Running…</p>
  if (state.error) return <Alert>{state.error.message}</Alert>
  if (!state.data) return <p className="text-sm text-slate-500">Press “Run” to execute the algorithm on the current data (read-only — nothing is changed).</p>
  return children(state.data)
}

/* ------------------------------- 1. FIFO ------------------------------- */
function FifoTab({ classes }) {
  const [classId, setClassId] = useState('')
  const [state, run] = useRunner(() => adminApi.insightFifo(classId))
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="w-80"><Field label="Class"><Select value={classId} onChange={(e) => setClassId(e.target.value)}>
          <option value="">Select a class…</option>
          {classes.map((c) => <option key={c.id} value={c.id}>{c.subject_code} — {c.faculty_name} ({c.pending_requests} waiting)</option>)}
        </Select></Field></div>
        <Button disabled={!classId} onClick={run}>Run</Button>
      </div>
      <Result state={state}>
        {(d) => (
          <div className="space-y-4">
            <p className="text-sm">{d.class.label}: <b>{d.class.enrolled}/{d.class.capacity}</b> seats filled, <Badge status={d.class.status} />. Queue order equals arrival order: <b>{d.order_is_arrival_order ? 'yes' : 'NO'}</b>.</p>
            <div className="grid gap-4 md:grid-cols-3">
              <Card title={`Queue before (${d.queue_before.length})`} padded={false}><Table rows={d.queue_before} rowKey={(r) => r.request_id} empty="Queue is empty." columns={[{ key: 'queue_seq', header: 'Seq' }, { key: 'student', header: 'Student' }]} /></Card>
              <Card title={`Would be accepted, in order (${d.simulation.would_accept_in_order.length} of ${d.simulation.seats_available} seats)`} padded={false}><Table rows={d.simulation.would_accept_in_order} rowKey={(r) => r.request_id} empty="None." columns={[{ key: 'queue_seq', header: 'Seq' }, { key: 'student', header: 'Student' }]} /></Card>
              <Card title="Left over after processing" padded={false}>
                <Table rows={[...d.simulation.would_be_turned_away_when_full.map((r) => ({ ...r, note: 'turned away — class full' })), ...d.simulation.would_remain_waiting.map((r) => ({ ...r, note: 'still waiting' }))]} rowKey={(r) => r.request_id} empty="None." columns={[{ key: 'queue_seq', header: 'Seq' }, { key: 'student', header: 'Student' }, { key: 'note', header: '' }]} />
              </Card>
            </div>
            <Complexity data={d.complexity} />
          </div>
        )}
      </Result>
    </div>
  )
}

/* ------------------------------ 2. Greedy ------------------------------ */
function GreedyTab({ subjects, classes }) {
  const [subjectId, setSubjectId] = useState('')
  const [preferred, setPreferred] = useState('')
  const [state, run] = useRunner(() => adminApi.insightGreedy({ subject_id: subjectId, preferred_class_id: preferred || null }))
  const subjectClasses = classes.filter((c) => String(c.subject_id) === String(subjectId))
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="w-72"><Field label="Subject"><Select value={subjectId} onChange={(e) => { setSubjectId(e.target.value); setPreferred('') }}>
          <option value="">Select a subject…</option>
          {subjects.map((s) => <option key={s.id} value={s.id}>{s.code} — {s.name}</option>)}
        </Select></Field></div>
        <div className="w-72"><Field label="Student's preferred class (optional)"><Select value={preferred} onChange={(e) => setPreferred(e.target.value)} disabled={!subjectId}>
          <option value="">No preference</option>
          {subjectClasses.map((c) => <option key={c.id} value={c.id}>{c.faculty_name} ({c.remaining} free)</option>)}
        </Select></Field></div>
        <Button disabled={!subjectId} onClick={run}>Run</Button>
      </div>
      <Result state={state}>
        {(d) => (
          <div className="space-y-4">
            <Alert kind="info" title="Greedy rule">{d.rule} Priority order: <b>{d.criteria_order.join(' > ')}</b>.</Alert>
            <Table rows={d.candidates} rowKey={(r) => r.class_id} columns={[
              { key: 'rank', header: 'Rank' },
              { key: 'faculty', header: 'Faculty', render: (r) => <span className={d.selected?.class_id === r.class_id ? 'font-bold text-brand-700' : ''}>{r.faculty}{d.selected?.class_id === r.class_id && ' ← selected'}</span> },
              { key: 'remaining', header: 'Free seats' }, { key: 'queue_length', header: 'Queue' },
              { key: 'slot_compatible', header: 'Slot OK', render: (r) => (r.slot_compatible ? 'yes' : 'no') },
              { key: 'available', header: 'Available', render: (r) => (r.available ? 'yes' : 'no') },
              { key: 'score', header: 'Priority vector', render: (r) => <code className="text-xs">[{r.score.join(', ')}]</code> },
            ]} />
            <p className="text-sm text-slate-700">{d.selected ? <>Selected: <b>{d.selected.faculty}</b>. </> : <b>No class is available. </b>}{d.reason}</p>
            <Complexity data={d.complexity} />
          </div>
        )}
      </Result>
    </div>
  )
}

/* --------------------------- 3. Graph colouring --------------------------- */
function ColoringTab() {
  const [state, run] = useRunner(() => adminApi.insightColoring())
  return (
    <div className="space-y-4">
      <Button onClick={run}>Run dry-run (nothing is saved)</Button>
      <Result state={state}>
        {(d) => (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
              <StatCard label="Offerings to place" value={d.to_place} hint={`${d.already_placed} already placed (kept fixed)`} />
              <StatCard label="Must-not-overlap edges" value={d.hard_edges} hint={`${d.soft_edges} preferred-apart edges`} />
              <StatCard label="States visited" value={d.nodes_visited} />
              <StatCard label="Backtracks" value={d.backtracks} tone={d.backtracking_required ? 'warn' : 'good'} hint={d.backtracking_required ? 'backtracking was required' : 'no backtracking needed'} />
              <StatCard label="Optional overlaps left" value={d.soft_overlaps} hint="optional subjects of a group sharing time" />
            </div>
            <Alert kind={d.status === 'OK' ? 'success' : 'error'}>{d.message}</Alert>
            <div className="grid gap-4 lg:grid-cols-2">
              <Card title={`Conflict edges involving unplaced offerings (${d.edges_total}${d.edges_total > d.edges.length ? `, first ${d.edges.length}` : ''})`} padded={false}>
                <div className="max-h-80 overflow-y-auto"><Table rows={d.edges} empty="No conflicts." columns={[
                  { key: 'a', header: 'Class A' }, { key: 'b', header: 'Class B' }, { key: 'reasons', header: 'Why they must not overlap', render: (e) => e.reasons.join('; ') },
                ]} /></div>
              </Card>
              <Card title="Slots it would assign" padded={false}>
                <div className="max-h-80 overflow-y-auto"><Table rows={d.assignments} rowKey={(a) => a.class_id} empty="Nothing to place." columns={[
                  { key: 'subject_code', header: 'Subject' }, { key: 'faculty', header: 'Faculty' }, { key: 'theory_slot', header: 'Theory slot' }, { key: 'lab_slot', header: 'Lab slot', render: (a) => a.lab_slot || '—' },
                ]} /></div>
              </Card>
            </div>
            {d.vertex_order && <p className="text-xs text-slate-500">Placement order (highest number of conflicts first): {d.vertex_order.join(' → ')}{d.vertex_order.length >= 40 ? ' …' : ''}</p>}
            <Complexity data={d.complexity} />
          </div>
        )}
      </Result>
    </div>
  )
}

/* ----------------------------- 4. Max flow ------------------------------ */
function FlowTab({ onRecorded }) {
  const [state, run] = useRunner(async () => { const r = await adminApi.runMaxFlow(); onRecorded(); return r })
  return (
    <div className="space-y-4">
      <Button onClick={run}>Run Edmonds-Karp</Button>
      <Result state={state}>
        {(d) => {
          const s = d.summary
          const pct = s.total_requested ? Math.round((s.max_flow / s.total_requested) * 100) : 100
          return (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                <StatCard label="Requested (student × subject)" value={s.total_requested} hint={`${s.distinct_students} distinct students`} />
                <StatCard label="Max feasible flow" value={s.max_flow} tone="good" hint="students that can be seated" />
                <StatCard label="Unaccommodated" value={s.unaccommodated} tone={s.unaccommodated ? 'bad' : 'good'} />
                <StatCard label="Free seats overall" value={s.total_free_seats} />
              </div>
              <div>
                <div className="mb-1 flex justify-between text-xs text-slate-500"><span>Accommodated {pct}%</span><span>{d.network.nodes} nodes · {d.network.edges} edges · {d.network.augmenting_paths} augmenting paths</span></div>
                <div className="h-3 overflow-hidden rounded-full bg-rose-200"><div className="h-3 bg-emerald-500" style={{ width: `${pct}%` }} /></div>
                <p className="mt-1 text-xs text-slate-500">Network: {d.network.layers}</p>
              </div>
              <div className="grid gap-4 lg:grid-cols-2">
                <Card title="Bottleneck classes (min-cut)" padded={false}>
                  <Table rows={d.bottleneck_classes} rowKey={(c) => c.class_id} empty="No bottleneck — all demand fits." columns={[
                    { key: 'subject_code', header: 'Subject' }, { key: 'faculty_name', header: 'Faculty' }, { key: 'free_seats', header: 'Free seats' }, { key: 'assigned', header: 'Assigned' },
                  ]} />
                </Card>
                <Card title="Per-subject outcome" padded={false}>
                  <Table rows={d.subjects} rowKey={(r) => r.subject_id} columns={[
                    { key: 'code', header: 'Subject' }, { key: 'demand', header: 'Demand' }, { key: 'accommodated', header: 'Seated' },
                    { key: 'unaccommodated', header: 'Unseated', render: (r) => <span className={r.unaccommodated ? 'font-bold text-rose-600' : ''}>{r.unaccommodated}</span> }, { key: 'free_seats', header: 'Free seats' },
                  ]} />
                </Card>
              </div>
              <Card title="Seat usage in the optimal allocation" padded={false}>
                <Table rows={d.classes} rowKey={(c) => c.class_id} columns={[
                  { key: 'subject_code', header: 'Class', render: (c) => `${c.subject_code} — ${c.faculty_name}` },
                  { key: 'bar', header: 'Assigned / free seats', render: (c) => (
                    <div className="flex items-center gap-2"><div className="h-2 w-40 rounded-full bg-slate-200"><div className={`h-2 rounded-full ${c.bottleneck ? 'bg-rose-500' : 'bg-emerald-500'}`} style={{ width: `${c.free_seats ? (c.assigned / c.free_seats) * 100 : 0}%` }} /></div><span className="text-xs">{c.assigned}/{c.free_seats}</span></div>) },
                  { key: 'b', header: '', render: (c) => (c.bottleneck ? <Badge status="FULL">bottleneck</Badge> : null) },
                ]} />
              </Card>
              {d.unaccommodated_students.length > 0 && (
                <Card title="Students who cannot be seated with current capacity" padded={false}>
                  <Table rows={d.unaccommodated_students} columns={[{ key: 'student', header: 'Student' }, { key: 'subject', header: 'Subject' }]} />
                </Card>
              )}
              <p className="text-xs text-slate-500">{d.note}</p>
              <Complexity data={d.complexity} />
            </div>
          )
        }}
      </Result>
    </div>
  )
}

function RunHistory({ state }) {
  return (
    <Card title="Algorithm execution status (recent runs)" padded={false}>
      <Async state={state} empty={<div className="p-5"><EmptyState title="No runs recorded yet">Timetable generation and max-flow runs are logged here.</EmptyState></div>}>
        {(rows) => <Table rows={rows} rowKey={(r) => r.id} columns={[
          { key: 'algorithm', header: 'Algorithm', render: (r) => r.algorithm.replaceAll('_', ' ') },
          { key: 'status', header: 'Status', render: (r) => <Badge status={r.status} /> },
          { key: 'summary', header: 'Summary', render: (r) => <code className="text-xs text-slate-600">{JSON.stringify({ ...r.summary, attempts: undefined })}</code> },
          { key: 'created_at', header: 'When', render: (r) => formatDateTime(r.created_at) },
        ]} />}
      </Async>
    </Card>
  )
}

export default function Insights() {
  const [tab, setTab] = useState('fifo')
  const lookups = useApi(async () => {
    const [classes, subjects] = await Promise.all([adminApi.classes(), adminApi.subjects()])
    return { classes, subjects }
  })
  const runs = useApi(() => adminApi.algorithmRuns())
  return (
    <>
      <PageHeader title="Algorithm insights" subtitle="Inputs, outputs and complexity of the four Phase 1 algorithms. These views are read-only — they never change registrations, queues or capacity; the normal workflow stays authoritative." />
      <div className="mb-4 flex flex-wrap gap-2">
        {TABS.map(([k, label]) => (
          <button key={k} onClick={() => setTab(k)} className={`rounded-lg border px-4 py-2 text-sm font-medium ${tab === k ? 'border-brand-600 bg-brand-600 text-white' : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-50'}`}>{label}</button>
        ))}
      </div>
      <div className="space-y-6">
        <Card title={TABS.find(([k]) => k === tab)[1]}>
          <p className="mb-4 text-sm text-slate-500">{WHERE[tab]}</p>
          <Async state={lookups}>
            {({ classes, subjects }) => (
              <>
                {tab === 'fifo' && <FifoTab key="fifo" classes={classes} />}
                {tab === 'greedy' && <GreedyTab key="greedy" classes={classes} subjects={subjects} />}
                {tab === 'coloring' && <ColoringTab key="coloring" />}
                {tab === 'flow' && <FlowTab key="flow" onRecorded={runs.reload} />}
              </>
            )}
          </Async>
        </Card>
        <RunHistory state={runs} />
      </div>
    </>
  )
}
