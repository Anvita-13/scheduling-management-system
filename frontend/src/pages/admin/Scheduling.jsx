import { useState } from 'react'
import { adminApi, timetableApi } from '../../api'
import TimetableGrid from '../../components/TimetableGrid'
import { Alert, Async, Badge, Button, Card, EmptyState, Field, Input, PageHeader, Select, StatCard, Table } from '../../components/ui'
import { useToast } from '../../components/Toast'
import { useAction, useApi } from '../../hooks/useApi'

function Clashes({ state }) {
  return (
    <Async state={state}>
      {(c) => {
        const problems = c.hard_clashes.length + c.student_clashes.length + c.unscheduled.length + c.no_room.length
        return (
          <div className="space-y-4">
            {problems === 0
              ? <Alert kind="success" title="No clashes">Every offering is placed, every part has a room, and no teacher, mandatory subject or student overlaps.</Alert>
              : <Alert kind="warning" title="Needs attention">Resolve the items below.</Alert>}
            {c.unscheduled.length > 0 && <Card title={`Offerings without a slot (${c.unscheduled.length})`} padded={false}>
              <Table rows={c.unscheduled} rowKey={(r) => r.class_id} columns={[{ key: 'subject_code', header: 'Subject' }, { key: 'faculty', header: 'Faculty' }]} />
            </Card>}
            {c.no_room.length > 0 && <Card title={`Offerings without a room (${c.no_room.length})`} padded={false}>
              <Table rows={c.no_room} rowKey={(r) => r.class_id} columns={[{ key: 'subject_code', header: 'Subject' }, { key: 'faculty', header: 'Faculty' }]} />
              <p className="px-5 pb-4 text-xs text-slate-500">Add a room of the right type/size below, or move the offering to a quieter slot.</p>
            </Card>}
            {c.hard_clashes.length > 0 && <Card title="Clashes that must be fixed" padded={false}>
              <Table rows={c.hard_clashes} columns={[{ key: 'a', header: 'Class A' }, { key: 'b', header: 'Class B' }, { key: 'reasons', header: 'Why', render: (r) => r.reasons.join('; ') }]} />
            </Card>}
            {c.student_clashes.length > 0 && <Card title="Students with overlapping classes" padded={false}>
              <Table rows={c.student_clashes} columns={[{ key: 'student', header: 'Student' }, { key: 'a', header: 'Class' }, { key: 'b', header: 'Overlaps' }]} />
            </Card>}
            <Card title={`Optional subjects sharing time (${c.shared_slot_options.length}) — informational`} padded={false}>
              {c.shared_slot_options.length === 0 ? <p className="p-5 text-sm text-slate-500">No optional subjects of one group overlap.</p> : (
                <>
                  <Table rows={c.shared_slot_options} columns={[{ key: 'a', header: 'Subject A' }, { key: 'b', header: 'Subject B' }, { key: 'reasons', header: 'Group', render: (r) => r.reasons[0] }]} />
                  <p className="px-5 pb-4 text-xs text-slate-500">Students of that group can take only one of each pair. The optimiser keeps these to a minimum.</p>
                </>
              )}
            </Card>
          </div>
        )
      }}
    </Async>
  )
}

function Rooms() {
  const toast = useToast()
  const { busy, run } = useAction(toast)
  const state = useApi(() => adminApi.rooms())
  const [room, setRoom] = useState({ name: '', kind: 'LECTURE', capacity: 60 })
  return (
    <Card title="Rooms">
      <p className="mb-3 text-sm text-slate-500">Only the type and size are entered. Which class gets which room is automatic: classes that meet at overlapping times are never given the same room, and labs go to lab rooms.</p>
      <form className="mb-3 flex flex-wrap items-end gap-2" onSubmit={(e) => { e.preventDefault(); run(() => adminApi.createRoom({ ...room, capacity: Number(room.capacity) }), { success: 'Room added; rooms reassigned', onDone: state.reload }) }}>
        <div className="w-36"><Field label="Name"><Input required value={room.name} onChange={(e) => setRoom({ ...room, name: e.target.value })} /></Field></div>
        <div className="w-32"><Field label="Type"><Select value={room.kind} onChange={(e) => setRoom({ ...room, kind: e.target.value })}><option value="LECTURE">Lecture hall</option><option value="LAB">Lab</option></Select></Field></div>
        <div className="w-28"><Field label="Seats"><Input type="number" min="1" value={room.capacity} onChange={(e) => setRoom({ ...room, capacity: e.target.value })} /></Field></div>
        <Button type="submit" busy={busy}>Add</Button>
      </form>
      <Async state={state}>
        {(rows) => (
          <div className="max-h-64 overflow-y-auto">
            <Table rows={rows} rowKey={(r) => r.id} empty="No rooms yet." columns={[
              { key: 'name', header: 'Room' }, { key: 'kind', header: 'Type', render: (r) => (r.kind === 'LAB' ? 'Lab' : 'Lecture hall') }, { key: 'capacity', header: 'Seats' },
              { key: 'x', header: '', className: 'text-right', render: (r) => <Button size="sm" variant="ghost" onClick={() => window.confirm(`Delete ${r.name}?`) && run(() => adminApi.deleteRoom(r.id), { onDone: state.reload })}>Delete</Button> },
            ]} />
          </div>
        )}
      </Async>
    </Card>
  )
}

export default function Scheduling() {
  const toast = useToast()
  const { busy, run } = useAction(toast)
  const dashboard = useApi(() => adminApi.dashboard())
  const clashes = useApi(() => adminApi.clashes())
  const entries = useApi(() => timetableApi.mine())
  const [report, setReport] = useState(null)
  const [failure, setFailure] = useState(null)
  const refresh = () => { dashboard.reload(); clashes.reload(); entries.reload() }

  async function autoAssign() {
    setFailure(null)
    try {
      const rep = await adminApi.autoAssign()
      setReport(rep)
      toast.success(rep.to_place ? `Placed ${rep.to_place} offering(s)` : 'Nothing to place')
    } catch (e) {
      setReport(null)
      setFailure(e.message)
      toast.error('The optimiser could not place everything')
    }
    refresh()
  }

  return (
    <>
      <PageHeader
        title="Scheduling"
        subtitle="The optimiser chooses slots for every offering that has none: it never puts one teacher in two overlapping slots, never overlaps a group's mandatory subjects with anything else in that group, keeps a theory part clear of its own lab, respects the number of rooms, and spreads optional subjects so students can combine them. Offerings you placed by hand stay where they are."
        actions={<>
          <Button variant="secondary" busy={busy} onClick={() => window.confirm('Un-place every offering that has no students, so the optimiser can redo them?') && run(() => adminApi.clearPlacements(), { success: (r) => `${r.cleared} offering(s) un-placed`, onDone: refresh })}>Clear unlocked slots</Button>
          <Button busy={busy} onClick={() => run(autoAssign)}>Auto-assign slots</Button>
        </>}
      />
      <div className="space-y-6">
        <Async state={dashboard}>
          {(d) => (
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              <StatCard label="Offerings" value={d.offerings} />
              <StatCard label="Without a slot" value={d.unscheduled} tone={d.unscheduled ? 'warn' : 'good'} />
              <StatCard label="Clashes" value={d.hard_clashes} tone={d.hard_clashes ? 'bad' : 'good'} />
              <StatCard label="Without a room" value={d.no_room} tone={d.no_room ? 'bad' : 'good'} />
            </div>
          )}
        </Async>
        {failure && <Alert kind="error" title="Slots could not be assigned">{failure}</Alert>}
        {report && (
          <Alert kind="success" title="Slots assigned">
            Placed {report.to_place} offering(s) ({report.already_placed} were already placed). The search visited {report.nodes_visited} states
            {report.backtracking_required ? ` and undid ${report.backtracks} choice(s) (backtracking was needed)` : ' without needing to backtrack'};
            {' '}{report.soft_overlaps} optional-subject overlap(s) remain.
            {report.rooms_unassigned.length > 0 && ` No room for: ${report.rooms_unassigned.join(', ')}.`}
          </Alert>
        )}
        <h2 className="text-lg font-semibold">Clash report</h2>
        <Clashes state={clashes} />
        <h2 className="text-lg font-semibold">Weekly timetable (all placed offerings)</h2>
        <Async state={entries}>
          {(rows) => rows.length === 0 ? <EmptyState title="Nothing placed yet">Run the optimiser or place offerings on the Offerings page.</EmptyState> : <TimetableGrid entries={rows} />}
        </Async>
        <Rooms />
      </div>
    </>
  )
}
