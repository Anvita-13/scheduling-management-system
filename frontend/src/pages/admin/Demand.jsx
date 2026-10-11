import { Fragment, useState } from 'react'
import { adminApi } from '../../api'
import CapacityEditor from '../../components/CapacityEditor'
import { Alert, Async, Badge, Button, Card, EmptyState, PageHeader, SeatBar, StatCard, Table } from '../../components/ui'
import { useApi } from '../../hooks/useApi'
import { formatDateTime } from '../../utils/format'

export default function Demand() {
  const state = useApi(() => adminApi.demand())
  const [open, setOpen] = useState(null)

  return (
    <>
      <PageHeader title="Demand & waitlist" subtitle="Where students still lack a seat. Increase capacity on the affected classes; waiting students are notified automatically." />
      <Async state={state}>
        {(d) => {
          const alerts = d.subjects.filter((s) => s.no_faculty_available)
          return (
            <div className="space-y-6">
              <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                <StatCard label="Unmet demand" value={d.total_unmet} tone={d.total_unmet ? 'bad' : 'good'} hint="students without a seat or request" />
                <StatCard label="Subjects without any open class" value={alerts.length} tone={alerts.length ? 'bad' : 'good'} />
                <StatCard label="Total enrolled" value={d.subjects.reduce((a, s) => a + s.enrolled, 0)} tone="good" />
                <StatCard label="Waiting in queues" value={d.subjects.reduce((a, s) => a + s.pending, 0)} />
              </div>
              {alerts.map((s) => (
                <Alert key={s.subject_id} kind="error" title={`No faculty available: ${s.code} — ${s.name}`}>
                  {s.unmet + s.pending} student(s) need a seat but every class is full or closed. Increase capacity below.
                </Alert>
              ))}
              <Card title="Demand per subject" padded={false}>
                <Table
                  rows={d.subjects}
                  rowKey={(r) => r.subject_id}
                  empty="No subjects."
                  columns={[
                    { key: 'code', header: 'Subject', render: (r) => <span><b>{r.code}</b> <span className="text-slate-500">{r.name}</span></span> },
                    { key: 'demand', header: 'Demand' },
                    { key: 'enrolled', header: 'Enrolled' },
                    { key: 'pending', header: 'Waiting' },
                    { key: 'unmet', header: 'Unmet', render: (r) => <span className={r.unmet ? 'font-bold text-rose-600' : ''}>{r.unmet}</span> },
                    { key: 'seats_remaining', header: 'Free seats' },
                    { key: 'x', header: '', className: 'text-right', render: (r) => <Button size="sm" variant="secondary" onClick={() => setOpen(open === r.subject_id ? null : r.subject_id)}>{open === r.subject_id ? 'Hide classes' : 'Adjust capacity'}</Button> },
                  ]}
                />
                {d.subjects.filter((s) => s.subject_id === open).map((s) => (
                  <Fragment key={s.subject_id}>
                    <div className="border-t border-slate-200 bg-slate-50 px-5 py-4">
                      <p className="mb-2 text-sm font-semibold">Classes for {s.code}</p>
                      <Table rows={s.classes} rowKey={(c) => c.id} columns={[
                        { key: 'faculty_name', header: 'Faculty' },
                        { key: 'seats', header: 'Seats', render: (c) => <SeatBar enrolled={c.enrolled_count} capacity={c.capacity} /> },
                        { key: 'status', header: 'Status', render: (c) => <Badge status={c.status} /> },
                        { key: 'cap', header: 'Capacity', render: (c) => <CapacityEditor key={`${c.id}-${c.capacity}`} cls={c} onChanged={state.reload} /> },
                      ]} />
                    </div>
                  </Fragment>
                ))}
              </Card>
              <Card title="Waitlist — students without a seat" padded={false}>
                {d.waitlist.length === 0 ? <div className="p-5"><EmptyState title="Nobody is waiting" /></div> : (
                  <Table rows={d.waitlist} rowKey={(r) => `${r.student_id}-${r.subject_id}`} columns={[
                    { key: 'student_name', header: 'Student' },
                    { key: 'roll_number', header: 'Roll no.' },
                    { key: 'subject_code', header: 'Subject' },
                    { key: 'since', header: 'Registered', render: (r) => formatDateTime(r.since) },
                  ]} />
                )}
              </Card>
            </div>
          )
        }}
      </Async>
    </>
  )
}
