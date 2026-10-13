import { useEffect } from 'react'
import { Link, useParams } from 'react-router-dom'
import { facultyApi } from '../../api'
import { Alert, Async, Badge, Button, Card, EmptyState, PageHeader, SeatBar, Table } from '../../components/ui'
import { useToast } from '../../components/Toast'
import { useAction, useApi } from '../../hooks/useApi'
import { formatDateTime } from '../../utils/format'

export default function ClassDetail() {
  const { classId } = useParams()
  const toast = useToast()
  const state = useApi(() => facultyApi.classDetail(classId), [classId])
  const { busy, run } = useAction(toast)

  // New requests arrive while the page is open - refresh quietly every 10 seconds.
  const { reload } = state
  useEffect(() => {
    const t = setInterval(reload, 10000)
    return () => clearInterval(t)
  }, [reload])

  return (
    <Async state={state}>
      {(c) => {
        const canAccept = c.status === 'OPEN' && c.remaining > 0
        return (
          <>
            <PageHeader
              title={`${c.subject_code} — ${c.subject_name}`}
              subtitle="Waiting students are listed in the exact order their requests arrived. Accept from the front of the queue."
              actions={
                <>
                  <Link to="/faculty/classes"><Button variant="secondary">← Classes</Button></Link>
                  <Button variant="danger" disabled={c.status !== 'OPEN'} busy={busy}
                    onClick={() => window.confirm('Close this class? Students still waiting will be rejected and notified.') &&
                      run(() => facultyApi.closeClass(c.id), { success: 'Class closed', onDone: state.reload })}>Close class</Button>
                </>
              }
            />
            <div className="space-y-6">
              <Card>
                <div className="mb-4 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700">
                  {c.theory_slot ? (
                    <>
                      <div><b>Theory {c.theory_slot}</b> — {c.theory_times}{c.room ? ` — room ${c.room}` : ''}</div>
                      {c.lab_slot && <div><b>Lab {c.lab_slot}</b> — {c.lab_times}{c.lab_room ? ` — room ${c.lab_room}` : ''}</div>}
                    </>
                  ) : 'Slot not assigned yet.'}
                </div>
                <div className="grid gap-6 md:grid-cols-4">
                  <div><p className="text-xs uppercase text-slate-500">Status</p><div className="mt-1"><Badge status={c.status} /></div></div>
                  <div className="md:col-span-2"><p className="mb-1 text-xs uppercase text-slate-500">Seats filled</p><SeatBar enrolled={c.enrolled_count} capacity={c.capacity} /></div>
                  <div><p className="text-xs uppercase text-slate-500">Seats remaining</p><p className="text-2xl font-bold">{c.remaining}</p></div>
                </div>
                {c.status === 'FULL' && <div className="mt-4"><Alert kind="warning">All seats are filled, so the class closed automatically. New requests are rejected and students are told the class is full.</Alert></div>}
                {c.status === 'CLOSED' && (
                  <div className="mt-4">
                    <Alert kind="info" title="This class is closed">
                      {c.reopen_requested
                        ? 'You have asked the administration to reopen it. You will be notified of their decision.'
                        : 'If more students need this class, you can ask the administration to reopen it.'}
                    </Alert>
                    {!c.reopen_requested && (
                      <div className="mt-3"><Button busy={busy} onClick={() => run(() => facultyApi.requestReopen(c.id), { success: 'Request sent to the administration', onDone: state.reload })}>Request reopening</Button></div>
                    )}
                  </div>
                )}
              </Card>

              <Card title={`Pending requests (${c.queue.length}) — first come, first served`} padded={false}>
                {c.queue.length === 0 ? (
                  <div className="p-5"><EmptyState title="No one is waiting">New requests will appear here in arrival order.</EmptyState></div>
                ) : (
                  <Table
                    rows={c.queue}
                    rowKey={(r) => r.request_id}
                    columns={[
                      { key: 'position', header: '#', className: 'w-12 font-bold' },
                      { key: 'student_name', header: 'Student' },
                      { key: 'roll_number', header: 'Roll no.' },
                      { key: 'requested_at', header: 'Requested', render: (r) => formatDateTime(r.requested_at) },
                      { key: 'actions', header: '', className: 'text-right whitespace-nowrap', render: (r) => r.is_front ? (
                        <div className="flex justify-end gap-2">
                          <Button size="sm" busy={busy} disabled={!canAccept}
                            onClick={() => run(() => facultyApi.acceptNext(c.id, r.request_id), { success: `${r.student_name} accepted`, onDone: state.reload })}>Accept</Button>
                          <Button size="sm" variant="secondary" busy={busy}
                            onClick={() => run(() => facultyApi.rejectNext(c.id, r.request_id), { success: `${r.student_name} declined`, onDone: state.reload })}>Decline</Button>
                        </div>
                      ) : <span className="text-xs text-slate-400">Waiting for earlier requests</span> },
                    ]}
                  />
                )}
              </Card>

              <Card title={`Accepted students (${c.accepted.length})`} padded={false}>
                <Table
                  rows={c.accepted}
                  rowKey={(r) => r.request_id}
                  empty="No students accepted yet."
                  columns={[
                    { key: 'student_name', header: 'Student' },
                    { key: 'roll_number', header: 'Roll no.' },
                    { key: 'accepted_at', header: 'Accepted', render: (r) => formatDateTime(r.accepted_at) },
                  ]}
                />
              </Card>
            </div>
          </>
        )
      }}
    </Async>
  )
}
