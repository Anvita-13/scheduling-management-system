import { timetableApi } from '../../api'
import { Async, EmptyState, PageHeader } from '../../components/ui'
import TimetableGrid from '../../components/TimetableGrid'
import { useApi } from '../../hooks/useApi'

export default function TimetablePage({ title = 'Timetable' }) {
  const state = useApi(() => timetableApi.mine())
  return (
    <>
      <PageHeader title={title} subtitle="The conflict-free timetable published by the administration." />
      <Async state={state}>
        {(entries) =>
          entries.length === 0 ? (
            <EmptyState title="No timetable yet">It will appear here once the administration generates it after registration ends.</EmptyState>
          ) : (
            <TimetableGrid entries={entries} />
          )
        }
      </Async>
    </>
  )
}
