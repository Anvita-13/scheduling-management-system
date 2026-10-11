import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { studentApi } from '../../api'
import { Alert, Async, Button, Card, Field, Input, PageHeader } from '../../components/ui'
import { useToast } from '../../components/Toast'
import { useAction, useApi } from '../../hooks/useApi'

export default function Credits() {
  const toast = useToast()
  const state = useApi(() => studentApi.profile())
  const { busy, run } = useAction(toast)
  const [value, setValue] = useState('')

  useEffect(() => { if (state.data) setValue(String(state.data.selected_credits ?? state.data.min_credits)) }, [state.data])

  return (
    <>
      <PageHeader title="Credit selection" subtitle="Choose how many credits you intend to take this term. The subjects you pick must fit within this number." />
      <Async state={state}>
        {(p) => {
          const n = Number(value)
          const valid = Number.isInteger(n) && n >= p.min_credits && n <= p.max_credits
          return (
            <div className="max-w-xl space-y-4">
              {!p.registration_open && <Alert kind="warning">Registration is closed, so credits can no longer be changed.</Alert>}
              {p.mandatory_subjects.length > 0 && (
                <Alert kind="info" title={`Group ${p.group_code}: mandatory subjects`}>
                  {p.mandatory_subjects.map((m) => `${m.code} (${m.credits} cr)`).join(', ')} are added automatically when you save, and count toward your load.
                </Alert>
              )}
              <Card title="Credit load">
                <form
                  className="space-y-4"
                  onSubmit={(e) => {
                    e.preventDefault()
                    run(() => studentApi.setCredits(n), { success: `Credit load set to ${n}`, onDone: state.reload })
                  }}
                >
                  <Field label={`Credits (allowed range ${p.min_credits}–${p.max_credits})`} hint={`You have already selected ${p.committed_credits} credits of subjects.`}>
                    <Input type="number" min={p.min_credits} max={p.max_credits} value={value} onChange={(e) => setValue(e.target.value)} />
                  </Field>
                  <input type="range" min={p.min_credits} max={p.max_credits} value={valid ? n : p.min_credits} onChange={(e) => setValue(e.target.value)} className="w-full accent-brand-600" aria-label="Credit slider" />
                  {!valid && <p className="text-sm text-rose-600">Enter a whole number between {p.min_credits} and {p.max_credits}.</p>}
                  <div className="flex items-center gap-3">
                    <Button type="submit" disabled={!valid || !p.registration_open} busy={busy}>Save credit load</Button>
                    {p.selected_credits != null && <Link to="/student/subjects" className="text-sm font-medium text-brand-700 underline">Continue to subjects →</Link>}
                  </div>
                </form>
              </Card>
            </div>
          )
        }}
      </Async>
    </>
  )
}
