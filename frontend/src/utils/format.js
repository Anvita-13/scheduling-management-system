export function formatDateTime(value) {
  if (!value) return '—'
  // The API returns UTC; naive timestamps (no zone) are treated as UTC.
  const iso = /[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

export const STATUS_STYLES = {
  OPEN: 'bg-emerald-100 text-emerald-800',
  FULL: 'bg-rose-100 text-rose-800',
  CLOSED: 'bg-slate-200 text-slate-700',
  PENDING: 'bg-amber-100 text-amber-800',
  ACCEPTED: 'bg-emerald-100 text-emerald-800',
  REJECTED: 'bg-rose-100 text-rose-800',
  CANCELLED: 'bg-slate-200 text-slate-700',
  ENROLLED: 'bg-emerald-100 text-emerald-800',
  REQUESTED: 'bg-amber-100 text-amber-800',
  SELECTED: 'bg-sky-100 text-sky-800',
  SUCCESS: 'bg-emerald-100 text-emerald-800',
  FAILED: 'bg-rose-100 text-rose-800',
}

export const REASON_TEXT = {
  CLASS_FULL: 'Class was full',
  CLASS_CLOSED: 'Class was closed',
  FACULTY_DECLINED: 'Declined by faculty',
  CANCELLED_BY_STUDENT: 'Cancelled by you',
}

export const NOTIFICATION_STYLES = {
  CLASS_FULL: 'bg-rose-500',
  CLASS_CLOSED: 'bg-slate-500',
  NO_FACULTY_AVAILABLE: 'bg-rose-600',
  REQUEST_ACCEPTED: 'bg-emerald-500',
  REQUEST_REJECTED: 'bg-rose-500',
  CAPACITY_INCREASED: 'bg-sky-500',
  TIMETABLE_GENERATED: 'bg-brand-600',
  NEW_JOIN_REQUEST: 'bg-amber-500',
}
