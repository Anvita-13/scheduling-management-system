import { Link } from 'react-router-dom'
import { studentApi } from '../../api'
import { Async, Badge, Button, Card, EmptyState, PageHeader, Table } from '../../components/ui'
import { useToast } from '../../components/Toast'
import { useAction, useApi } from '../../hooks/useApi'
import { REASON_TEXT, formatDateTime } from '../../utils/format'

export default function Requests() {
  const toast = useToast()
  const state = useApi(() => studentApi.requests())
  const { busy, run } = useAction(toast)

  return (
    <>
      <PageHeader title="Request status" subtitle="Every join request you have sent and what happened to it." />
      <Async state={state} empty={<EmptyState title="No requests yet"><Link className="underline" to="/student/subjects">Choose a subject and faculty</Link> to send your first request.</EmptyState>}>
        {(rows) => (
          <Card padded={false}>
            <Table
              rows={rows}
              rowKey={(r) => r.id}
              columns={[
                { key: 'subject', header: 'Subject', render: (r) => <span><b>{r.subject_code}</b> <span className="text-slate-500">{r.subject_name}</span></span> },
                { key: 'faculty_name', header: 'Faculty' },
                { key: 'slots', header: 'Slots', render: (r) => <span className="text-xs">{r.theory_slot}{r.lab_slot ? ` + ${r.lab_slot}` : ''}</span> },
                { key: 'status', header: 'Status', render: (r) => <Badge status={r.status} /> },
                { key: 'detail', header: 'Details', render: (r) => r.status === 'PENDING'
                  ? <span className="text-slate-700">Position <b>#{r.queue_position}</b> in the queue</span>
                  : <span className="text-slate-500">{REASON_TEXT[r.decision_reason] || r.decision_reason || ''}</span> },
                { key: 'requested_at', header: 'Sent', render: (r) => formatDateTime(r.requested_at) },
                { key: 'actions', header: '', className: 'text-right', render: (r) => (
                  r.status === 'PENDING'
                    ? <Button size="sm" variant="secondary" busy={busy} onClick={() => run(() => studentApi.cancelRequest(r.id), { success: 'Request cancelled', onDone: state.reload })}>Cancel</Button>
                    : (r.status === 'REJECTED' ? <Link to={`/student/subjects/${r.subject_id}`}><Button size="sm">Choose another faculty</Button></Link> : null)
                ) },
              ]}
            />
          </Card>
        )}
      </Async>
    </>
  )
}
