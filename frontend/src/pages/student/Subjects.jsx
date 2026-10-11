import { Link } from 'react-router-dom'
import { studentApi } from '../../api'
import { Alert, Async, Badge, Button, Card, PageHeader, Table } from '../../components/ui'
import { useToast } from '../../components/Toast'
import { useAction, useApi } from '../../hooks/useApi'

const ROLE_BADGE = { MANDATORY: ['ENROLLED', 'Mandatory'], GROUP: ['SELECTED', 'Your group'] }

export default function Subjects() {
  const toast = useToast()
  const state = useApi(async () => {
    const [profile, subjects] = await Promise.all([studentApi.profile(), studentApi.subjects()])
    return { profile, subjects }
  })
  const { busy, run } = useAction(toast)

  return (
    <>
      <PageHeader title="Subjects" subtitle="Mandatory subjects of your group are added automatically. Pick any others you want, then choose a faculty option for each." />
      <Async state={state}>
        {({ profile, subjects }) => {
          // your group's subjects first, then everything else
          const sorted = [...subjects].sort((a, b) => (b.group_role ? 1 : 0) - (a.group_role ? 1 : 0) || a.code.localeCompare(b.code))
          return (
            <div className="space-y-4">
              {profile.selected_credits == null ? (
                <Alert kind="warning" title="Choose your credits first">You must set a credit load before selecting subjects. <Link to="/student/credits" className="font-semibold underline">Go to credit selection</Link></Alert>
              ) : (
                <Alert kind="info">Credit load: <b>{profile.committed_credits}</b> of <b>{profile.selected_credits}</b> credits used. Slot clashes are blocked automatically — see the <Link to="/student/slots" className="font-semibold underline">Slot View</Link> to compare options.</Alert>
              )}
              <Card padded={false}>
                <Table
                  rows={sorted}
                  rowKey={(r) => r.id}
                  empty="No subjects have been created yet."
                  columns={[
                    { key: 'code', header: 'Code', className: 'font-medium' },
                    { key: 'name', header: 'Subject', render: (r) => <span>{r.name}{r.group_role && <Badge className="ml-2" status={ROLE_BADGE[r.group_role][0]}>{ROLE_BADGE[r.group_role][1]}</Badge>}</span> },
                    { key: 'credits', header: 'Credits', render: (r) => (r.has_lab ? `${r.credits}+${r.lab_credits} (T+L)` : `${r.credits} (T)`) },
                    { key: 'avail', header: 'Options with seats', render: (r) => `${r.classes_available} of ${r.classes_total}` },
                    { key: 'status', header: 'My status', render: (r) => (r.selected ? <Badge status={r.registration_status} /> : <span className="text-slate-400">—</span>) },
                    {
                      key: 'actions', header: '', className: 'text-right whitespace-nowrap',
                      render: (r) => !r.selected ? (
                        <Button size="sm" busy={busy} disabled={profile.selected_credits == null || !profile.registration_open}
                          onClick={() => run(() => studentApi.selectSubject(r.id), { success: `${r.code} added`, onDone: state.reload })}>Select</Button>
                      ) : (
                        <div className="flex justify-end gap-2">
                          {r.registration_status !== 'ENROLLED' && <Link to={`/student/subjects/${r.id}`}><Button size="sm">{r.registration_status === 'REQUESTED' ? 'View options' : 'Choose faculty'}</Button></Link>}
                          {r.registration_status !== 'ENROLLED' && r.group_role !== 'MANDATORY' && (
                            <Button size="sm" variant="secondary" busy={busy} disabled={!profile.registration_open}
                              onClick={() => run(() => studentApi.dropSubject(r.id), { success: `${r.code} removed`, onDone: state.reload })}>Drop</Button>
                          )}
                        </div>
                      ),
                    },
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
