import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Loader2, RefreshCw, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { startHearingPrep } from '@/lib/api'
import { useRisks, useSummary, useTimeline } from '@/hooks/useCases'
import type { Case, CaseSummary } from '@/lib/types'
import RiskPanel from './RiskPanel'
import TimelineView from './TimelineView'

type Tab = 'summary' | 'risks' | 'timeline' | 'prep'

const TABS: { id: Tab; label: string }[] = [
  { id: 'summary', label: 'Summary' },
  { id: 'risks', label: 'Risks' },
  { id: 'timeline', label: 'Timeline' },
  { id: 'prep', label: 'Hearing prep' },
]

interface CaseDashboardProps {
  activeCase: Case
  onClose: () => void
}

export default function CaseDashboard({ activeCase, onClose }: CaseDashboardProps) {
  const [tab, setTab] = useState<Tab>('summary')

  return (
    <div className="flex h-full flex-col bg-slate-50">
      <div className="shrink-0 flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3">
        <p className="text-sm font-semibold text-slate-900">Case insights</p>
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100"
          aria-label="Close insights"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div role="tablist" className="shrink-0 flex gap-1 border-b border-slate-200 bg-white px-3">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            type="button"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            className={cn(
              'border-b-2 px-2.5 py-2 text-xs font-medium transition-colors',
              tab === t.id
                ? 'border-brand text-brand'
                : 'border-transparent text-slate-500 hover:text-slate-800',
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {tab === 'summary' && <SummaryTab caseId={activeCase.id} />}
        {tab === 'risks' && <RisksTab caseId={activeCase.id} />}
        {tab === 'timeline' && <TimelineTab caseId={activeCase.id} />}
        {tab === 'prep' && <PrepTab activeCase={activeCase} />}
      </div>
    </div>
  )
}

// ─── Shared bits ──────────────────────────────────────────────────────────────

function Loading({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center gap-2 py-10 text-sm text-slate-400">
      <Loader2 className="h-5 w-5 animate-spin" />
      {label}
    </div>
  )
}

function ErrorNote({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700 flex items-center justify-between gap-2">
      <span>{message}</span>
      {onRetry && (
        <button type="button" onClick={onRetry} className="inline-flex items-center gap-1 font-medium hover:underline">
          <RefreshCw className="h-3 w-3" /> Retry
        </button>
      )}
    </div>
  )
}

function ListSection({ title, items }: { title: string; items: string[] }) {
  if (!items?.length) return null
  return (
    <section className="space-y-1">
      <h3 className="text-2xs font-semibold uppercase tracking-wider text-slate-400">{title}</h3>
      <ul className="list-disc pl-4 space-y-0.5 text-sm text-slate-700">
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </section>
  )
}

function SummaryView({ summary }: { summary: CaseSummary }) {
  return (
    <div className="space-y-4">
      {summary.summary && <p className="text-sm text-slate-800 leading-relaxed">{summary.summary}</p>}
      <ListSection title="Parties" items={summary.parties} />
      <ListSection title="Claims / charges" items={summary.charges_or_claims} />
      <ListSection title="Key dates" items={(summary.key_dates ?? []).map((d) => `${d.date} — ${d.event}`)} />
      <ListSection title="Evidence" items={summary.evidence} />
      <ListSection title="Open issues" items={summary.open_issues} />
    </div>
  )
}

// ─── Tabs ─────────────────────────────────────────────────────────────────────

function SummaryTab({ caseId }: { caseId: string }) {
  const { data, isLoading, isError, refetch } = useSummary(caseId)
  if (isLoading) return <Loading label="Reading case documents…" />
  if (isError || !data) return <ErrorNote message="Could not load the summary." onRetry={() => refetch()} />
  if (data.error) return <ErrorNote message={data.error} onRetry={() => refetch()} />
  return <SummaryView summary={data} />
}

function RisksTab({ caseId }: { caseId: string }) {
  const { data, isLoading, isError, refetch } = useRisks(caseId)
  if (isLoading) return <Loading label="Analysing risks…" />
  if (isError || !data) return <ErrorNote message="Could not load risks." onRetry={() => refetch()} />
  if (data.error) return <ErrorNote message={data.error} onRetry={() => refetch()} />
  return <RiskPanel risks={data.risks} message={data.message} />
}

function TimelineTab({ caseId }: { caseId: string }) {
  const { data, isLoading, isError, refetch } = useTimeline(caseId)
  if (isLoading) return <Loading label="Building timeline…" />
  if (isError || !data) return <ErrorNote message="Could not load the timeline." onRetry={() => refetch()} />
  return <TimelineView events={data.timeline} />
}

function PrepTab({ activeCase }: { activeCase: Case }) {
  const [hearingDate, setHearingDate] = useState(activeCase.hearing_date ?? '')
  const prep = useMutation({ mutationFn: () => startHearingPrep(activeCase.id, hearingDate) })
  const strategy = prep.data?.strategy

  return (
    <div className="space-y-4">
      <form
        className="flex items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          prep.mutate()
        }}
      >
        <label className="flex-1 text-xs text-slate-500">
          Hearing date
          <input
            type="date"
            required
            value={hearingDate}
            onChange={(e) => setHearingDate(e.target.value)}
            className="mt-1 block w-full rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-sm text-slate-800"
          />
        </label>
        <button
          type="submit"
          disabled={prep.isPending || !hearingDate}
          className="rounded-lg bg-brand px-3 py-2 text-xs font-medium text-white hover:bg-brand-hover disabled:opacity-50"
        >
          {prep.data ? 'Regenerate' : 'Generate prep sheet'}
        </button>
      </form>

      {prep.isPending && <Loading label="Preparing hearing strategy…" />}
      {prep.isError && <ErrorNote message="Could not generate the prep sheet." />}

      {prep.data && !prep.isPending && (
        <div className="space-y-4">
          <p className="text-xs text-slate-500">
            {prep.data.documents.length} document(s) · {prep.data.high_risk_count} high-severity risk(s)
          </p>
          {strategy?.error ? (
            <ErrorNote message={strategy.error} />
          ) : (
            strategy && (
              <>
                {strategy.opening_statement_outline && (
                  <section className="space-y-1">
                    <h3 className="text-2xs font-semibold uppercase tracking-wider text-slate-400">
                      Opening statement
                    </h3>
                    <p className="text-sm text-slate-700">{strategy.opening_statement_outline}</p>
                  </section>
                )}
                <ListSection title="Key arguments" items={strategy.key_arguments} />
                <ListSection title="Anticipated objections" items={strategy.anticipated_objections} />
                <ListSection title="Witness considerations" items={strategy.witness_considerations} />
                <ListSection title="Document priorities" items={strategy.document_priorities} />
                <ListSection title="Procedural checklist" items={strategy.procedural_checklist} />
              </>
            )
          )}
        </div>
      )}
    </div>
  )
}
