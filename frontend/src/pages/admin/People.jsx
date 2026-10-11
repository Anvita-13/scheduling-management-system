import { useState } from 'react'
import { adminApi } from '../../api'
import { Async, Button, Card, Field, Input, PageHeader, Table } from '../../components/ui'
import { useToast } from '../../components/Toast'
import { useAction, useApi } from '../../hooks/useApi'

function CreateUser({ kind, onCreated }) {
  const toast = useToast()
  const { busy, run } = useAction(toast)
  const empty = { name: '', email: '', password: '', code: '', department: '', group: '' }
  const [f, setF] = useState(empty)
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const isFaculty = kind === 'faculty'

  return (
    <Card title={`Add ${isFaculty ? 'faculty member' : 'student'}`}>
      <form className="grid gap-4 md:grid-cols-3" onSubmit={async (e) => {
        e.preventDefault()
        const body = isFaculty
          ? { name: f.name, email: f.email, password: f.password, employee_code: f.code, department: f.department }
          : { name: f.name, email: f.email, password: f.password, roll_number: f.code, group_code: f.group || null }
        const api = isFaculty ? adminApi.createFaculty : adminApi.createStudent
        const res = await run(() => api(body), { success: 'Account created', onDone: onCreated })
        if (res) setF(empty)
      }}>
        <Field label="Full name"><Input required value={f.name} onChange={set('name')} /></Field>
        <Field label="Email"><Input required type="email" value={f.email} onChange={set('email')} /></Field>
        <Field label="Initial password" hint="At least 8 characters"><Input required type="password" minLength={8} value={f.password} onChange={set('password')} /></Field>
        <Field label={isFaculty ? 'Employee code' : 'Roll number'}><Input required value={f.code} onChange={set('code')} /></Field>
        {isFaculty && <Field label="Department"><Input value={f.department} onChange={set('department')} /></Field>}
        {!isFaculty && <Field label="Group (programme-semester)" hint="e.g. CSE-S3; decides mandatory subjects"><Input value={f.group} onChange={set('group')} /></Field>}
        <div className="flex items-end"><Button type="submit" busy={busy} className="w-full">Create account</Button></div>
      </form>
    </Card>
  )
}

export default function People() {
  const [tab, setTab] = useState('faculty')
  const state = useApi(() => (tab === 'faculty' ? adminApi.faculty() : adminApi.students()), [tab])
  return (
    <>
      <PageHeader title="People" subtitle="Faculty and student accounts." />
      <div className="mb-4 inline-flex rounded-lg border border-slate-300 bg-white p-1">
        {['faculty', 'students'].map((t) => (
          <button key={t} onClick={() => setTab(t)} className={`rounded-md px-4 py-1.5 text-sm font-medium capitalize ${tab === t ? 'bg-brand-600 text-white' : 'text-slate-600 hover:bg-slate-100'}`}>{t}</button>
        ))}
      </div>
      <div className="space-y-6">
        <CreateUser kind={tab} onCreated={state.reload} />
        <Card padded={false}>
          <Async state={state}>
            {(rows) => tab === 'faculty' ? (
              <Table rows={rows} rowKey={(r) => r.user_id} columns={[
                { key: 'name', header: 'Name' }, { key: 'email', header: 'Email' }, { key: 'employee_code', header: 'Code' },
                { key: 'department', header: 'Department' }, { key: 'subjects', header: 'Subjects', render: (r) => r.subjects.join(', ') || '—' },
              ]} />
            ) : (
              <Table rows={rows} rowKey={(r) => r.user_id} columns={[
                { key: 'name', header: 'Name' }, { key: 'email', header: 'Email' }, { key: 'roll_number', header: 'Roll no.' }, { key: 'group_code', header: 'Group', render: (r) => r.group_code || '—' },
                { key: 'selected_credits', header: 'Credit target', render: (r) => r.selected_credits ?? '—' }, { key: 'max_credits', header: 'Max credits' },
              ]} />
            )}
          </Async>
        </Card>
      </div>
    </>
  )
}
