import { useState } from 'react'
import { adminApi } from '../api'
import { useAction } from '../hooks/useApi'
import { useToast } from './Toast'
import { Button, Input } from './ui'

/** Inline capacity control for one class. Increasing a FULL class reopens it (backend rule). */
export default function CapacityEditor({ cls, onChanged }) {
  const toast = useToast()
  const { busy, run } = useAction(toast)
  const [value, setValue] = useState(String(cls.capacity))
  const n = Number(value)
  const valid = Number.isInteger(n) && n >= cls.enrolled_count && n <= 1000
  return (
    <div className="flex items-center gap-2">
      <Input type="number" min={cls.enrolled_count} className="!w-20 !py-1" value={value} onChange={(e) => setValue(e.target.value)} aria-label={`Capacity for ${cls.subject_code} ${cls.faculty_name}`} />
      <Button size="sm" busy={busy} disabled={!valid || n === cls.capacity}
        onClick={() => run(() => adminApi.setCapacity(cls.id, n), { success: `Capacity set to ${n}`, onDone: onChanged })}>Save</Button>
    </div>
  )
}
