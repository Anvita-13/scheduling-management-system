import { Link } from 'react-router-dom'
import { studentApi } from '../../api'
import { Alert, Async, Badge, Button, Card, PageHeader, StatCard, Table } from '../../components/ui'
import { useApi } from '../../hooks/useApi'

export default function StudentDashboard() {
  const state = useApi(async () => {
    const [profile, subjects, requests] = await Promise.all([studentApi.profile(), studentApi.subjects(), studentApi.requests()])
    return { profile, subjects, requests }
  })

  return (
    <>
      <PageHeader title="My dashboard" subtitle="Your registration progress at a glance." />
      <Async state={state}>
        {({ profile, subjects, requests }) => {
          const mine = subjects.filter((s) => s.selected)
          const enrolled = mine.filter((s) => s.registration_status === 'ENROLLED')
          const needAction = mine.filter((s) => s.registration_status === 'SELECTED')
          const pending = requests.filter((r) => r.status === 'PENDING')
          return (
            <div className="space-y-6">
              {!profile.registration_open && <Alert kind="warning" title="Registration is closed">New requests are not accepted right now. The administration may reopen it for students without a seat.</Alert>}
              {profile.selected_credits == null && profile.registration_open && (
                <Alert kind="info" title="Start here">Choose how many credits you want to take. <Link className="font-semibold underline" to="/student/credits">Select credits →</Link></Alert>
              )}
              {needAction.length > 0 && (
                <Alert kind="warning" title={`${needAction.length} subject(s) still need a faculty`}>
                  {needAction.map((s) => s.code).join(', ')} — <Link className="font-semibold underline" to="/student/subjects">choose a faculty</Link>
                </Alert>
              )}
              <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                <StatCard label="Credit target" value={profile.selected_credits ?? '—'} hint={`Allowed ${profile.min_credits}–${profile.max_credits}`} />
                <StatCard label="Credits selected" value={profile.committed_credits} hint="across chosen subjects" />
                <StatCard label="Enrolled subjects" value={enrolled.length} tone="good" />
                <StatCard label="Pending requests" value={pending.length} tone={pending.length ? 'warn' : 'default'} />
              </div>
              <Card title="My subjects" actions={<Link to="/student/subjects"><Button variant="secondary" size="sm">Manage</Button></Link>}>
                <Table
                  rows={mine}
                  rowKey={(r) => r.id}
                  empty="You have not selected any subjects yet."
                  columns={[
                    { key: 'code', header: 'Code' },
                    { key: 'name', header: 'Subject' },
                    { key: 'credits', header: 'Credits' },
                    { key: 'status', header: 'Status', render: (r) => <Badge status={r.registration_status} /> },
                  ]}
                />
              </Card>
            </div>
          )
        }}
      </Async>
    </>
  )
}
