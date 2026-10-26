import type { TimelineEvent } from '@/lib/types'

interface TimelineViewProps {
  events: TimelineEvent[]
}

export default function TimelineView({ events }: TimelineViewProps) {
  if (events.length === 0) {
    return <p className="text-xs text-slate-400 text-center py-6">No dated events found in the documents.</p>
  }

  return (
    <ol className="relative ml-2 border-l border-slate-200 space-y-4">
      {events.map((ev, i) => (
        <li key={i} className="ml-4">
          <span className="absolute -left-[5px] mt-1.5 h-2.5 w-2.5 rounded-full border-2 border-white bg-brand" />
          <p className="text-xs font-semibold text-brand">{ev.date}</p>
          <p className="text-sm text-slate-800">{ev.event}</p>
          {ev.source && <p className="text-2xs text-slate-400">{ev.source}</p>}
        </li>
      ))}
    </ol>
  )
}
