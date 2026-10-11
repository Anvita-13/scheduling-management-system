import { STATUS_STYLES } from '../utils/format'

export function Spinner({ label = 'Loading…' }) {
  return (
    <div role="status" className="flex items-center gap-3 text-slate-500 text-sm">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-slate-300 border-t-brand-600" />
      {label}
    </div>
  )
}

export function Card({ title, actions, children, className = '', padded = true }) {
  return (
    <section className={`rounded-xl border border-slate-200 bg-white shadow-sm ${className}`}>
      {(title || actions) && (
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-5 py-3">
          <h2 className="font-semibold text-slate-800">{title}</h2>
          <div className="flex items-center gap-2">{actions}</div>
        </header>
      )}
      <div className={padded ? 'p-5' : ''}>{children}</div>
    </section>
  )
}

export function PageHeader({ title, subtitle, actions }) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-500 max-w-3xl">{subtitle}</p>}
      </div>
      <div className="flex gap-2">{actions}</div>
    </div>
  )
}

const BUTTONS = {
  primary: 'bg-brand-600 text-white hover:bg-brand-700 disabled:bg-brand-600/50',
  secondary: 'bg-white text-slate-700 border border-slate-300 hover:bg-slate-50 disabled:text-slate-400',
  danger: 'bg-rose-600 text-white hover:bg-rose-700 disabled:bg-rose-600/50',
  ghost: 'text-brand-700 hover:bg-brand-50 disabled:text-slate-400',
}

export function Button({ variant = 'primary', size = 'md', className = '', busy, children, ...props }) {
  const sizes = size === 'sm' ? 'px-2.5 py-1 text-xs' : 'px-4 py-2 text-sm'
  return (
    <button
      type="button"
      {...props}
      disabled={props.disabled || busy}
      className={`inline-flex items-center justify-center gap-2 rounded-lg font-medium transition disabled:cursor-not-allowed ${sizes} ${BUTTONS[variant]} ${className}`}
    >
      {busy && <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" />}
      {children}
    </button>
  )
}

export function Badge({ status, children, className = '' }) {
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${STATUS_STYLES[status] || 'bg-slate-100 text-slate-700'} ${className}`}>
      {children ?? status}
    </span>
  )
}

export function Alert({ kind = 'error', title, children, onRetry }) {
  const styles = {
    error: 'border-rose-200 bg-rose-50 text-rose-800',
    success: 'border-emerald-200 bg-emerald-50 text-emerald-800',
    warning: 'border-amber-200 bg-amber-50 text-amber-900',
    info: 'border-sky-200 bg-sky-50 text-sky-900',
  }
  return (
    <div role={kind === 'error' ? 'alert' : 'status'} className={`rounded-lg border px-4 py-3 text-sm ${styles[kind]}`}>
      {title && <p className="font-semibold">{title}</p>}
      <div>{children}</div>
      {onRetry && <button onClick={onRetry} className="mt-2 font-medium underline">Try again</button>}
    </div>
  )
}

export function EmptyState({ title, children }) {
  return (
    <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-6 py-10 text-center">
      <p className="font-medium text-slate-700">{title}</p>
      {children && <p className="mt-1 text-sm text-slate-500">{children}</p>}
    </div>
  )
}

/** Standard loading / error wrapper so every page handles all three states the same way. */
export function Async({ state, children, empty }) {
  if (state.loading) return <Spinner />
  if (state.error) return <Alert title="Something went wrong" onRetry={state.reset}>{state.error.message}</Alert>
  if (empty && (Array.isArray(state.data) ? state.data.length === 0 : false)) return empty
  return children(state.data)
}

export function StatCard({ label, value, hint, tone = 'default' }) {
  const tones = { default: 'text-slate-900', warn: 'text-amber-600', bad: 'text-rose-600', good: 'text-emerald-600' }
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className={`mt-1 text-3xl font-bold ${tones[tone]}`}>{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  )
}

export function Field({ label, hint, children }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block font-medium text-slate-700">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-slate-500">{hint}</span>}
    </label>
  )
}

export const inputClass =
  'w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500'

export function Input(props) {
  return <input {...props} className={`${inputClass} ${props.className || ''}`} />
}

export function Select({ children, ...props }) {
  return <select {...props} className={`${inputClass} ${props.className || ''}`}>{children}</select>
}

export function Table({ columns, rows, rowKey, empty = 'Nothing to show.' }) {
  if (!rows.length) return <EmptyState title={empty} />
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
            {columns.map((c) => <th key={c.key} className={`px-3 py-2 font-medium ${c.className || ''}`}>{c.header}</th>)}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((r, i) => (
            <tr key={rowKey ? rowKey(r) : i} className="hover:bg-slate-50/60">
              {columns.map((c) => <td key={c.key} className={`px-3 py-2 align-middle ${c.className || ''}`}>{c.render ? c.render(r) : r[c.key]}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function SeatBar({ enrolled, capacity }) {
  const pct = capacity ? Math.min(100, Math.round((enrolled / capacity) * 100)) : 100
  const color = pct >= 100 ? 'bg-rose-500' : pct >= 75 ? 'bg-amber-500' : 'bg-emerald-500'
  return (
    <div className="min-w-[110px]">
      <div className="flex justify-between text-xs text-slate-600"><span>{enrolled}/{capacity}</span><span>{pct}%</span></div>
      <div className="mt-1 h-1.5 rounded-full bg-slate-200"><div className={`h-1.5 rounded-full ${color}`} style={{ width: `${pct}%` }} /></div>
    </div>
  )
}

export function Modal({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 z-40 grid place-items-center bg-slate-900/40 p-4" role="dialog" aria-modal="true" aria-label={title}>
      <div className="w-full max-w-lg rounded-xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3">
          <h3 className="font-semibold">{title}</h3>
          <button onClick={onClose} aria-label="Close" className="text-slate-500 hover:text-slate-800">✕</button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  )
}
