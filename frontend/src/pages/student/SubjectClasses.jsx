import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { studentApi } from '../../api'
import { Alert, Async, Badge, Button, Card, PageHeader, SeatBar, Table } from '../../components/ui'
import { useToast } from '../../components/Toast'
import { useApi } from '../../hooks/useApi'

export default function SubjectClasses() {
  const { subjectId } = useParams()
  const toast = useToast()
  const state = useApi(() => studentApi.classOptions(subjectId), [subjectId])
  const [busy, setBusy] = useState(false)
  const [fullNotice, setFullNotice] = useState(null)

  async function send(classId) {
    setBusy(true)
    setFullNotice(null)
    try {
      const res = await studentApi.requestClass(classId)
      toast.success(res.message)
    } catch (e) {
      if (e.code === 'CLASS_FULL') setFullNotice({ message: e.message, suggestion: e.body?.suggestion })
      else toast.error(e.message)  // e.g. SLOT_CLASH: the message names the clashing subject
    } finally {
      setBusy(false)
      state.reload()
    }
  }

  async function cancel(options) {
    const mine = options.find((o) => o.my_request_status === 'PENDING')
    if (!mine) return
    const reqs = await studentApi.requests()
    const req = reqs.find((r) => r.class_id === mine.class_id && r.status === 'PENDING')
    if (!req) return
    try {
      await studentApi.cancelRequest(req.id)
      toast.success('Request cancelled — you can pick another faculty')
    } catch (e) { toast.error(e.message) }
    state.reload()
  }

  return (
    <Async state={state}>
      {({ subject, options, any_available }) => {
        const pending = options.find((o) => o.my_request_status === 'PENDING')
        const enrolled = options.find((o) => o.my_request_status === 'ACCEPTED')
        return (
          <>
            <PageHeader
              title={`${subject.code} — ${subject.name}`}
              subtitle={`${subject.credits}${subject.has_lab ? `+${subject.lab_credits}` : ''} credits. ${subject.has_lab ? 'Each faculty option is a fixed theory + lab pair: choosing a faculty gives you that faculty\'s own lab slot too. ' : ''}Requests are served first-come-first-served by each faculty.`}
              actions={<Link to="/student/subjects"><Button variant="secondary">← Back</Button></Link>}
            />
            <div className="space-y-4">
              {enrolled && <Alert kind="success" title="You are enrolled">You have a seat in this subject. Nothing more to do.</Alert>}
              {pending && (
                <Alert kind="info" title="Request sent">
                  Waiting in the queue of {pending.faculty_name}. You can cancel it to choose someone else.
                  <div className="mt-2"><Button size="sm" variant="secondary" onClick={() => cancel(options)}>Cancel my request</Button></div>
                </Alert>
              )}
              {fullNotice && (
                <Alert kind="warning" title="That class is full">
                  {fullNotice.message}
                  {fullNotice.suggestion && (
                    <div className="mt-2"><Button size="sm" busy={busy} onClick={() => send(fullNotice.suggestion.class_id)}>Request {fullNotice.suggestion.faculty_name} instead</Button></div>
                  )}
                </Alert>
              )}
              {!any_available && !enrolled && !pending && (
                <Alert kind="error" title="No option can be taken right now">Every option is full, unscheduled, or clashes with a class you already hold. The administration has been alerted if nothing has seats.</Alert>
              )}
              <Card padded={false}>
                <Table
                  rows={options}
                  rowKey={(r) => r.class_id}
                  columns={[
                    { key: 'faculty_name', header: 'Faculty', className: 'font-medium', render: (r) => (
                      <span>{r.faculty_name}{r.recommended && <span className="ml-2 rounded-full bg-brand-100 px-2 py-0.5 text-xs font-semibold text-brand-700">Suggested</span>}</span>
                    ) },
                    { key: 'theory', header: 'Theory slot', render: (r) => r.theory_slot ? <><b>{r.theory_slot}</b><div className="text-xs text-slate-500">{r.theory_times}</div></> : <span className="text-slate-400">No slot yet</span> },
                    ...(subject.has_lab ? [{ key: 'lab', header: 'Lab slot', render: (r) => r.lab_slot ? <><b>{r.lab_slot}</b><div className="text-xs text-slate-500">{r.lab_times}</div></> : <span className="text-slate-400">—</span> }] : []),
                    { key: 'seats', header: 'Seats', render: (r) => <SeatBar enrolled={r.enrolled_count} capacity={r.capacity} /> },
                    { key: 'queue_length', header: 'Waiting' },
                    { key: 'status', header: 'Class', render: (r) => <Badge status={r.status} /> },
                    { key: 'action', header: '', className: 'text-right', render: (r) => r.my_request_status ? <Badge status={r.my_request_status}>Your request: {r.my_request_status}</Badge> : r.clash_with.length > 0 ? (
                      <span className="text-xs font-medium text-rose-600">Clashes with {r.clash_with.join(', ')}</span>
                    ) : !r.scheduled ? <span className="text-xs text-slate-400">Not scheduled</span> : (
                      <Button size="sm" busy={busy} disabled={Boolean(pending || enrolled)} onClick={() => send(r.class_id)}>{r.status === 'OPEN' && r.remaining > 0 ? 'Send request' : 'Request (full)'}</Button>
                    ) },
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
