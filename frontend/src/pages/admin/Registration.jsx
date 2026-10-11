import { useEffect, useState } from 'react'
import { adminApi } from '../../api'
import { Alert, Async, Badge, Button, Card, Field, Input, PageHeader, StatCard } from '../../components/ui'
import { useToast } from '../../components/Toast'
import { useAction, useApi } from '../../hooks/useApi'

export default function Registration() {
  const toast = useToast()
  const state = useApi(() => adminApi.registration())
  const { busy, run } = useAction(toast)
  const [credits, setCredits] = useState({ min: 12, max: 24 })

  useEffect(() => { if (state.data) setCredits({ min: state.data.min_credits, max: state.data.max_credits }) }, [state.data])

  return (
    <>
      <PageHeader title="Registration period" subtitle="Open or close registration and set the allowed credit range. Monitoring numbers update as students register." />
      <Async state={state}>
        {(r) => {
          const open = r.phase === 'OPEN'
          return (
            <div className="space-y-6">
              <Card title="Period status" actions={<Badge status={open ? 'OPEN' : 'CLOSED'} />}>
                <p className="mb-4 text-sm text-slate-600">
                  {open ? 'Students can currently select credits, subjects and send join requests.'
                        : 'Registration is closed. Students cannot send requests. Review demand, increase capacity and generate the timetable — or reopen the period for students who still need a seat.'}
                </p>
                <Button variant={open ? 'danger' : 'primary'} busy={busy}
                  onClick={() => run(() => adminApi.updateRegistration({ phase: open ? 'CLOSED' : 'OPEN' }),
                    { success: open ? 'Registration closed — students were notified' : 'Registration opened — students were notified', onDone: state.reload })}>
                  {open ? 'Close registration' : 'Reopen registration'}
                </Button>
              </Card>
              <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
                <StatCard label="Students" value={r.students} />
                <StatCard label="Chose credits" value={r.students_with_credits} />
                <StatCard label="Registrations" value={r.registrations} />
                <StatCard label="Enrolled" value={r.enrolled} tone="good" />
                <StatCard label="Pending requests" value={r.pending_requests} tone={r.pending_requests ? 'warn' : 'default'} />
              </div>
              <Card title="Allowed credit range">
                <form className="flex flex-wrap items-end gap-4" onSubmit={(e) => {
                  e.preventDefault()
                  run(() => adminApi.updateRegistration({ min_credits: Number(credits.min), max_credits: Number(credits.max) }), { success: 'Credit range saved', onDone: state.reload })
                }}>
                  <div className="w-32"><Field label="Minimum"><Input type="number" min="1" value={credits.min} onChange={(e) => setCredits({ ...credits, min: e.target.value })} /></Field></div>
                  <div className="w-32"><Field label="Maximum"><Input type="number" min="1" value={credits.max} onChange={(e) => setCredits({ ...credits, max: e.target.value })} /></Field></div>
                  <Button type="submit" busy={busy}>Save</Button>
                </form>
                <div className="mt-3"><Alert kind="info">A student's personal maximum can be lower than this range but never higher.</Alert></div>
              </Card>
            </div>
          )
        }}
      </Async>
    </>
  )
}
