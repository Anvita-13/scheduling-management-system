import { Link } from 'react-router-dom'
import { adminApi, notificationApi } from '../../api'
import { Alert, Async, Button, Card, PageHeader, StatCard } from '../../components/ui'
import { useApi } from '../../hooks/useApi'
import { NOTIFICATION_STYLES, formatDateTime } from '../../utils/format'

export default function AdminDashboard() {
  const state = useApi(async () => {
    const [dash, alerts] = await Promise.all([adminApi.dashboard(), notificationApi.list(true)])
    return { dash, alerts }
  })
  return (
    <>
      <PageHeader title="Management dashboard" subtitle="Registration progress, class capacity and system alerts." />
      <Async state={state}>
        {({ dash: d, alerts }) => (
          <div className="space-y-6">
            {d.unscheduled > 0 || d.hard_clashes > 0 || d.no_room > 0 ? (
              <Alert kind="warning" title="Scheduling needs attention">
                {d.unscheduled} offering(s) without a slot, {d.hard_clashes} clash(es), {d.no_room} without a room.{' '}
                <Link to="/admin/scheduling" className="font-semibold underline">Open Scheduling</Link>
              </Alert>
            ) : (
              <Alert kind="success" title="Schedule is clash-free">All {d.offerings} offerings are placed with rooms. <Link to="/admin/slot-chart" className="font-semibold underline">View the slot chart</Link></Alert>
            )}
            {d.registration.phase === 'CLOSED' && <Alert kind="warning" title="Registration is closed">Review <Link className="font-semibold underline" to="/admin/demand">unmet demand</Link> and add seats where needed.</Alert>}
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              <StatCard label="Offerings" value={d.offerings} hint={`${d.subjects} subjects · ${d.faculty} faculty`} />
              <StatCard label="Without a slot" value={d.unscheduled} tone={d.unscheduled ? 'warn' : 'good'} />
              <StatCard label="Clashes" value={d.hard_clashes} tone={d.hard_clashes ? 'bad' : 'good'} hint="should always be 0" />
              <StatCard label="Unmet demand" value={d.unmet_demand} tone={d.unmet_demand ? 'bad' : 'good'} hint="students without a seat" />
              <StatCard label="Seats filled" value={`${d.total_enrolled}/${d.total_capacity}`} />
              <StatCard label="Pending requests" value={d.registration.pending_requests} tone={d.registration.pending_requests ? 'warn' : 'default'} />
              <StatCard label="Full classes" value={d.full_classes} />
              <StatCard label="Registration" value={d.registration.phase === 'OPEN' ? 'Open' : 'Closed'} />
            </div>
            <Card title={`System alerts (${alerts.length} unread)`} actions={<Link to="/admin/notifications"><Button size="sm" variant="secondary">All notifications</Button></Link>} padded={false}>
              {alerts.length === 0 ? <p className="p-5 text-sm text-slate-500">No unread alerts.</p> : (
                <ul className="divide-y divide-slate-100">
                  {alerts.slice(0, 6).map((n) => (
                    <li key={n.id} className="flex items-start gap-3 px-5 py-3 text-sm">
                      <span className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${NOTIFICATION_STYLES[n.type] || 'bg-slate-400'}`} />
                      <div><p>{n.message}</p><p className="text-xs text-slate-400">{formatDateTime(n.created_at)}</p></div>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
        )}
      </Async>
    </>
  )
}
