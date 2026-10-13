import { useState } from 'react'
import { Link } from 'react-router-dom'
import { studentApi } from '../../api'
import { Alert, Async, Badge, Button, Card, PageHeader, Table } from '../../components/ui'
import { useToast } from '../../components/Toast'
import { useAction, useApi } from '../../hooks/useApi'

export default function Subjects() {
  const toast = useToast()
  const state = useApi(async () => {
    const [profile, subjects] = await Promise.all([studentApi.profile(), studentApi.subjects()])
    return { profile, subjects }
  })
  const { busy, run } = useAction(toast)
  const [hideClash, setHideClash] = useState(false)

  return (
    <>
      <PageHeader title="Subjects" subtitle="Pick any subjects you like within your credit load. Subjects that meet at the same time as one you already hold are marked." />
      <Async state={state}>
        {({ profile, subjects }) => {
          const sorted = subjects.filter((s) => !hideClash || s.selected || s.clashes_with.length === 0)
          return (
            <div className="space-y-4">
              {profile.selected_credits == null ? (
                <Alert kind="warning" title="Choose your credits first">You must set a credit load before selecting subjects. <Link to="/student/credits" className="font-semibold underline">Go to credit selection</Link></Alert>
              ) : (
                <Alert kind="info">Credit load: <b>{profile.committed_credits}</b> of <b>{profile.selected_credits}</b> credits used. Slot clashes are blocked automatically — see the <Link to="/student/slots" className="font-semibold underline">Slot View</Link> to compare options.</Alert>
              )}
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="accent-brand-600" checked={hideClash} onChange={(e) => setHideClash(e.target.checked)} /> Hide subjects that clash with the ones I have picked</label>
              <Card padded={false}>
                <Table
                  rows={sorted}
                  rowKey={(r) => r.id}
                  empty="No subjects have been created yet."
                  columns={[
                    { key: 'code', header: 'Code', className: 'font-medium' },
                    { key: 'name', header: 'Subject', render: (r) => (
                      <div>
                        <span>{r.name}</span>
                        {r.clashes_with.length > 0 && (
                          <div className="mt-1 text-xs font-medium text-rose-600">Clash: {r.clashes_with.map((c) => `${c.code}. ${c.message}`).join(' ')}</div>
                        )}
                      </div>
                    ) },
                    { key: 'credits', header: 'Credits', render: (r) => (r.has_lab ? `${r.credits}+${r.lab_credits} (T+L)` : `${r.credits} (T)`) },
                    { key: 'avail', header: 'Options with seats', render: (r) => `${r.classes_available} of ${r.classes_total}` },
                    { key: 'status', header: 'My status', render: (r) => (r.selected ? <Badge status={r.registration_status} /> : <span className="text-slate-400">—</span>) },
                    {
                      key: 'actions', header: '', className: 'text-right whitespace-nowrap',
                      render: (r) => !r.selected ? (
                        <Button size="sm" busy={busy} disabled={profile.selected_credits == null || !profile.registration_open || r.clashes_with.length > 0}
                          onClick={() => run(() => studentApi.selectSubject(r.id), { success: `${r.code} added`, onDone: state.reload })}>Select</Button>
                      ) : (
                        <div className="flex justify-end gap-2">
                          {r.registration_status !== 'ENROLLED' && <Link to={`/student/subjects/${r.id}`}><Button size="sm">{r.registration_status === 'REQUESTED' ? 'View options' : 'Choose faculty'}</Button></Link>}
                          {r.registration_status !== 'ENROLLED' && (
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
