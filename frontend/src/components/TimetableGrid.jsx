import { DAYS } from '../utils/format'

/** Weekly grid: rows = time ranges, columns = days. `entries` come from GET /timetable. */
export default function TimetableGrid({ entries, showFaculty = true }) {
  const days = DAYS.filter((d) => entries.some((e) => e.day === d))
  const times = [...new Set(entries.map((e) => `${e.start_time}-${e.end_time}`))].sort()
  const cell = (day, time) => entries.filter((e) => e.day === day && `${e.start_time}-${e.end_time}` === time)

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <th className="px-3 py-2 font-medium">Time</th>
            {days.map((d) => <th key={d} className="px-3 py-2 font-medium">{d}</th>)}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {times.map((t) => (
            <tr key={t}>
              <td className="whitespace-nowrap px-3 py-3 font-medium text-slate-600">{t.replace('-', ' – ')}</td>
              {days.map((d) => (
                <td key={d} className="px-2 py-2 align-top">
                  {cell(d, t).map((e) => (
                    <div key={e.entry_id} className={`mb-1 rounded-lg border px-2.5 py-1.5 ${e.component === 'LAB' ? 'border-emerald-200 bg-emerald-50' : 'border-brand-100 bg-brand-50'}`}>
                      <p className="font-semibold text-brand-900">{e.subject_code} <span className="text-xs font-normal text-slate-500">{e.component === 'LAB' ? 'Lab' : 'Theory'} · {e.slot}</span></p>
                      <p className="text-xs text-slate-600">{e.subject_name}</p>
                      {showFaculty && <p className="text-xs text-slate-500">{e.faculty_name}</p>}
                      {e.room && <p className="text-xs text-slate-500">Room {e.room}</p>}
                    </div>
                  ))}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
