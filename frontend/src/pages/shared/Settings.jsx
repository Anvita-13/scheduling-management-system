import { useState } from 'react'
import { authApi } from '../../api'
import { useAuth } from '../../auth/AuthContext'
import { Button, Card, Field, Input, PageHeader } from '../../components/ui'
import { useToast } from '../../components/Toast'
import { useAction } from '../../hooks/useApi'

function ProfileForm() {
  const { user, refresh } = useAuth()
  const toast = useToast()
  const { busy, run } = useAction(toast)
  const [name, setName] = useState(user.name)
  const [email, setEmail] = useState(user.email)
  const [password, setPassword] = useState('')
  const emailChanged = email.trim().toLowerCase() !== user.email.toLowerCase()

  return (
    <Card title="Your details">
      <form className="grid gap-4 md:grid-cols-2" onSubmit={async (e) => {
        e.preventDefault()
        const body = { name: name.trim() }
        if (emailChanged) { body.email = email.trim(); body.current_password = password }
        const res = await run(() => authApi.updateProfile(body), { success: 'Details updated' })
        if (res) { setPassword(''); refresh(res) }
      }}>
        <Field label="Full name"><Input required minLength={2} value={name} onChange={(e) => setName(e.target.value)} /></Field>
        <Field label="Email"><Input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
        {emailChanged && (
          <Field label="Current password" hint="Needed to change your email">
            <Input required type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </Field>
        )}
        <div className="flex items-end"><Button type="submit" busy={busy}>Save changes</Button></div>
      </form>
    </Card>
  )
}

function PasswordForm() {
  const toast = useToast()
  const { busy, run } = useAction(toast)
  const [f, setF] = useState({ current: '', next: '', again: '' })
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const mismatch = f.again !== '' && f.next !== f.again

  return (
    <Card title="Change password">
      <form className="grid gap-4 md:grid-cols-3" onSubmit={async (e) => {
        e.preventDefault()
        if (mismatch) return
        const res = await run(() => authApi.changePassword(f.current, f.next), { success: 'Password changed' })
        if (res) setF({ current: '', next: '', again: '' })
      }}>
        <Field label="Current password"><Input required type="password" value={f.current} onChange={set('current')} /></Field>
        <Field label="New password" hint="At least 8 characters"><Input required type="password" minLength={8} value={f.next} onChange={set('next')} /></Field>
        <Field label="Repeat new password" hint={mismatch ? 'The passwords do not match' : ''}><Input required type="password" value={f.again} onChange={set('again')} /></Field>
        <div><Button type="submit" busy={busy} disabled={mismatch}>Change password</Button></div>
      </form>
    </Card>
  )
}

export default function Settings() {
  return (
    <>
      <PageHeader title="Settings" subtitle="Change your name, email or password." />
      <div className="space-y-6">
        <ProfileForm />
        <PasswordForm />
      </div>
    </>
  )
}
