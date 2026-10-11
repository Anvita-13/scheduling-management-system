import { notificationApi } from '../../api'
import { Async, Button, Card, EmptyState, PageHeader } from '../../components/ui'
import { useToast } from '../../components/Toast'
import { useAction, useApi } from '../../hooks/useApi'
import { NOTIFICATION_STYLES, formatDateTime } from '../../utils/format'

export default function NotificationsPage() {
  const toast = useToast()
  const state = useApi(() => notificationApi.list())
  const { busy, run } = useAction(toast)

  const unread = state.data?.filter((n) => !n.is_read).length || 0
  return (
    <>
      <PageHeader
        title="Notifications"
        subtitle="Updates about your requests, classes and the timetable."
        actions={<Button variant="secondary" disabled={!unread} busy={busy} onClick={() => run(() => notificationApi.markAllRead(), { success: 'All marked as read', onDone: state.reload })}>Mark all as read</Button>}
      />
      <Async state={state} empty={<EmptyState title="No notifications yet">You will see updates here as things happen.</EmptyState>}>
        {(items) => (
          <Card padded={false}>
            <ul className="divide-y divide-slate-100">
              {items.map((n) => (
                <li key={n.id} className={`flex items-start gap-3 px-5 py-4 ${n.is_read ? '' : 'bg-brand-50/50'}`}>
                  <span className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${NOTIFICATION_STYLES[n.type] || 'bg-slate-400'}`} />
                  <div className="flex-1">
                    <p className={`text-sm ${n.is_read ? 'text-slate-600' : 'font-medium text-slate-900'}`}>{n.message}</p>
                    <p className="mt-0.5 text-xs text-slate-400">{formatDateTime(n.created_at)}</p>
                  </div>
                  {!n.is_read && (
                    <Button size="sm" variant="ghost" onClick={() => run(() => notificationApi.markRead(n.id), { onDone: state.reload })}>Mark read</Button>
                  )}
                </li>
              ))}
            </ul>
          </Card>
        )}
      </Async>
    </>
  )
}
