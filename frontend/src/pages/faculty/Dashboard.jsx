import { Link } from 'react-router-dom'
import { facultyApi } from '../../api'
import { Async, Badge, Button, Card, PageHeader, SeatBar, StatCard, Table } from '../../components/ui'
import { useApi } from '../../hooks/useApi'

export default function FacultyDashboard() {
  const state = useApi(() => facultyApi.dashboard())
  return (
    <>
      <PageHeader title="Faculty dashboard" subtitle="Your classes, waiting students and seat availability." />
      <Async state={state}>
        {(d) => (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              <StatCard label="My classes" value={d.classes} hint={`${d.open_classes} open`} />
              <StatCard label="Waiting requests" value={d.pending_requests} tone={d.pending_requests ? 'warn' : 'default'} hint="in first-come-first-served order" />
              <StatCard label="Enrolled students" value={d.enrolled_students} tone="good" />
              <StatCard label="Total seats" value={d.total_capacity} />
            </div>
            <Card title="Classes" actions={<Link to="/faculty/classes"><Button size="sm" variant="secondary">All classes</Button></Link>} padded={false}>
              <Table
                rows={d.class_list}
                rowKey={(r) => r.id}
                empty="You have not been assigned any classes yet."
                columns={[
                  { key: 'subject_code', header: 'Subject', render: (r) => <span><b>{r.subject_code}</b> <span className="text-slate-500">{r.subject_name}</span></span> },
                  { key: 'slot', header: 'Slot', render: (r) => <span className="text-xs">{r.theory_slot || '—'}{r.lab_slot ? ` + ${r.lab_slot}` : ''}</span> },
                  { key: 'seats', header: 'Seats', render: (r) => <SeatBar enrolled={r.enrolled_count} capacity={r.capacity} /> },
                  { key: 'pending_requests', header: 'Waiting' },
                  { key: 'status', header: 'Status', render: (r) => <Badge status={r.status} /> },
                  { key: 'go', header: '', className: 'text-right', render: (r) => <Link to={`/faculty/classes/${r.id}`}><Button size="sm">Open</Button></Link> },
                ]}
              />
            </Card>
          </div>
        )}
      </Async>
    </>
  )
}
