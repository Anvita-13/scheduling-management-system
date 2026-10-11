import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { notificationApi } from '../api'
import { useAuth } from '../auth/AuthContext'

const NAV = {
  ADMIN: [
    ['/admin', 'Dashboard', true],
    ['/admin/offerings', 'Offerings & Slots'],
    ['/admin/slot-chart', 'Slot Chart'],
    ['/admin/scheduling', 'Scheduling'],
    ['/admin/demand', 'Demand & Waitlist'],
    ['/admin/registration', 'Registration'],
    ['/admin/people', 'People'],
    ['/admin/insights', 'Algorithm Insights'],
    ['/admin/notifications', 'Notifications'],
  ],
  FACULTY: [
    ['/faculty', 'Dashboard', true],
    ['/faculty/classes', 'My Classes'],
    ['/faculty/timetable', 'Timetable'],
    ['/faculty/notifications', 'Notifications'],
  ],
  STUDENT: [
    ['/student', 'Dashboard', true],
    ['/student/credits', 'Credit Selection'],
    ['/student/subjects', 'Subjects'],
    ['/student/slots', 'Slot View'],
    ['/student/requests', 'Request Status'],
    ['/student/timetable', 'Timetable'],
    ['/student/notifications', 'Notifications'],
  ],
}

export default function DashboardLayout() {
  const { user, logout } = useAuth()
  const [unread, setUnread] = useState(0)
  const [open, setOpen] = useState(false)
  const location = useLocation()

  // Poll the unread badge every 15s and whenever the user navigates.
  useEffect(() => {
    let alive = true
    const load = () => notificationApi.unreadCount().then((r) => alive && setUnread(r.unread)).catch(() => {})
    load()
    const t = setInterval(load, 15000)
    return () => { alive = false; clearInterval(t) }
  }, [location.pathname])

  useEffect(() => setOpen(false), [location.pathname])

  const items = NAV[user.role]
  const roleLabel = { ADMIN: 'Management', FACULTY: 'Faculty', STUDENT: 'Student' }[user.role]

  return (
    <div className="flex min-h-full">
      <aside className={`fixed inset-y-0 left-0 z-30 w-64 transform bg-brand-900 text-indigo-100 transition-transform md:static md:translate-x-0 ${open ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="px-5 py-5">
          <p className="text-xs uppercase tracking-widest text-indigo-300">{roleLabel}</p>
          <p className="text-lg font-bold leading-tight text-white">College Scheduling</p>
        </div>
        <nav className="space-y-1 px-3" aria-label="Main">
          {items.map(([to, label, end]) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center justify-between rounded-lg px-3 py-2 text-sm font-medium ${isActive ? 'bg-white/15 text-white' : 'hover:bg-white/10'}`}
            >
              {label}
              {label === 'Notifications' && unread > 0 && (
                <span className="rounded-full bg-rose-500 px-2 py-0.5 text-xs font-bold text-white">{unread}</span>
              )}
            </NavLink>
          ))}
        </nav>
      </aside>
      {open && <div className="fixed inset-0 z-20 bg-black/30 md:hidden" onClick={() => setOpen(false)} />}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3">
          <button className="rounded-md p-2 text-slate-600 hover:bg-slate-100 md:hidden" onClick={() => setOpen(true)} aria-label="Open menu">☰</button>
          <div className="hidden md:block" />
          <div className="flex items-center gap-4">
            <div className="text-right text-sm">
              <p className="font-semibold text-slate-800">{user.name}</p>
              <p className="text-xs text-slate-500">{user.email}</p>
            </div>
            <button onClick={logout} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50">Sign out</button>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto p-4 md:p-8"><Outlet /></main>
      </div>
    </div>
  )
}
