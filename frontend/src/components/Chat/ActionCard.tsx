import { useState } from 'react'
import { CalendarPlus, Check, Copy, FileDown, Loader2, Mail } from 'lucide-react'
import { downloadReportPdf } from '@/lib/api'
import { buildIcs } from '@/lib/ics'
import type { CalendarAction, DraftAction, EmailAction, ReportAction } from '@/lib/types'

// ─── File helpers ─────────────────────────────────────────────────────────────

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function slug(text: string) {
  return text.replace(/[^a-z0-9]+/gi, '-').replace(/^-|-$/g, '').slice(0, 60) || 'file'
}

// ─── Buttons ──────────────────────────────────────────────────────────────────

const buttonClass =
  'inline-flex items-center gap-1.5 rounded-lg border border-[#1F3D6E]/20 bg-white px-2.5 py-1.5 text-xs font-medium text-[#1F3D6E] hover:bg-[#1F3D6E]/5 disabled:opacity-50 transition-colors'

function EmailButtons({ action }: { action: EmailAction }) {
  const [copied, setCopied] = useState(false)
  const mailto =
    `mailto:${encodeURIComponent(action.to)}` +
    `?subject=${encodeURIComponent(action.subject)}&body=${encodeURIComponent(action.body)}`

  return (
    <>
      <a href={mailto} className={buttonClass}>
        <Mail className="h-3.5 w-3.5" /> Open in mail app
      </a>
      <button
        type="button"
        className={buttonClass}
        onClick={async () => {
          await navigator.clipboard.writeText(`Subject: ${action.subject}\n\n${action.body}`)
          setCopied(true)
          setTimeout(() => setCopied(false), 1500)
        }}
      >
        {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
        {copied ? 'Copied' : 'Copy'}
      </button>
    </>
  )
}

function CalendarButton({ action }: { action: CalendarAction }) {
  const ics = buildIcs(action)
  if (!ics) {
    return <span className="text-xs text-slate-500">No date given — add one to create a calendar file.</span>
  }
  return (
    <button
      type="button"
      className={buttonClass}
      onClick={() => saveBlob(new Blob([ics], { type: 'text/calendar' }), `${slug(action.title)}.ics`)}
    >
      <CalendarPlus className="h-3.5 w-3.5" /> Download .ics
    </button>
  )
}

function ReportButton({ action, caseId }: { action: ReportAction; caseId: string }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(false)
  return (
    <>
      <button
        type="button"
        className={buttonClass}
        disabled={busy}
        onClick={async () => {
          setBusy(true)
          setError(false)
          try {
            const blob = await downloadReportPdf(caseId, { title: action.title, sections: action.sections })
            saveBlob(blob, `${slug(action.title)}.pdf`)
          } catch {
            setError(true)
          } finally {
            setBusy(false)
          }
        }}
      >
        {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FileDown className="h-3.5 w-3.5" />}
        Download PDF
      </button>
      {error && <span className="text-xs text-red-600">Could not create the PDF.</span>}
    </>
  )
}

// ─── Card ─────────────────────────────────────────────────────────────────────

const LABELS: Record<DraftAction['action_type'], string> = {
  email: 'Email draft',
  calendar: 'Calendar event',
  pdf_report: 'PDF report',
}

export default function ActionCard({ action, caseId }: { action: DraftAction; caseId: string }) {
  return (
    <div className="mt-3 rounded-lg border border-rose-200 bg-rose-50/50 p-3">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-rose-700">
        {LABELS[action.action_type] ?? 'Action'} · review before using
      </p>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        {action.action_type === 'email' && <EmailButtons action={action} />}
        {action.action_type === 'calendar' && <CalendarButton action={action} />}
        {action.action_type === 'pdf_report' && <ReportButton action={action} caseId={caseId} />}
      </div>
    </div>
  )
}
