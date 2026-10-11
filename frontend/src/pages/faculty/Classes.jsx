import { Link } from 'react-router-dom'
import { facultyApi } from '../../api'
import { Async, Badge, Button, Card, EmptyState, PageHeader, SeatBar } from '../../components/ui'
import { useApi } from '../../hooks/useApi'

export default function FacultyClasses() {
  const state = useApi(() => facultyApi.classes())
  return (
    <>
      <PageHeader title="My classes" subtitle="Subjects you teach, with live capacity information." />
      <Async state={state} empty={<EmptyState title="No classes assigned">The administration has not assigned you to a subject yet.</EmptyState>}>
        {(classes) => (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {classes.map((c) => (
              <Card key={c.id} title={`${c.subject_code} — ${c.subject_name}`} actions={<Badge status={c.status} />}>
                <div className="space-y-3 text-sm">
                  <div className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
                    {c.theory_slot ? (
                      <>
                        <div><b>{c.theory_slot}</b> · {c.theory_times}{c.room ? ` · ${c.room}` : ''}</div>
                        {c.lab_slot && <div><b>Lab {c.lab_slot}</b> · {c.lab_times}{c.lab_room ? ` · ${c.lab_room}` : ''}</div>}
                      </>
                    ) : 'Slot not assigned yet'}
                  </div>
                  <SeatBar enrolled={c.enrolled_count} capacity={c.capacity} />
                  <div className="flex justify-between text-slate-600">
                    <span>{c.remaining} seat(s) remaining</span>
                    <span>{c.pending_requests} waiting</span>
                  </div>
                  {c.status !== 'OPEN' && <p className="text-xs text-rose-600">This class is {c.status === 'FULL' ? 'full' : 'closed'} and no longer accepts requests.</p>}
                  <Link to={`/faculty/classes/${c.id}`}><Button className="w-full">Manage queue & students</Button></Link>
                </div>
              </Card>
            ))}
          </div>
        )}
      </Async>
    </>
  )
}
