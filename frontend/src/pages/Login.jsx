import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { ROLE_HOME, useAuth } from '../auth/AuthContext'
import { Alert, Button, Field, Input } from '../components/ui'

export default function Login() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to={ROLE_HOME[user.role]} replace />

  async function submit(e) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const u = await login(email.trim(), password)
      navigate(ROLE_HOME[u.role], { replace: true })
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid min-h-full place-items-center bg-gradient-to-br from-brand-900 to-brand-600 p-4">
      <form onSubmit={submit} className="w-full max-w-md space-y-5 rounded-2xl bg-white p-8 shadow-xl">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-brand-600">Welcome</p>
          <h1 className="text-2xl font-bold text-slate-900">College Scheduling Management System</h1>
          <p className="mt-1 text-sm text-slate-500">Sign in with your college account. Management, faculty and students use the same page.</p>
        </div>
        {error && <Alert>{error}</Alert>}
        <Field label="Email">
          <Input type="email" required autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} />
        </Field>
        <Field label="Password">
          <Input type="password" required autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </Field>
        <Button type="submit" busy={busy} className="w-full">Sign in</Button>
      </form>
    </div>
  )
}
