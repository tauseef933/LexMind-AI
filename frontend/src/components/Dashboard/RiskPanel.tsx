import { AlertTriangle } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Risk, RiskSeverity } from '@/lib/types'

const SEVERITY_STYLES: Record<RiskSeverity, string> = {
  HIGH: 'bg-red-50 text-red-700 border-red-200',
  MEDIUM: 'bg-amber-50 text-amber-700 border-amber-200',
  LOW: 'bg-slate-50 text-slate-600 border-slate-200',
}

const SEVERITY_ORDER: Record<RiskSeverity, number> = { HIGH: 0, MEDIUM: 1, LOW: 2 }

interface RiskPanelProps {
  risks: Risk[]
  message?: string
}

export default function RiskPanel({ risks, message }: RiskPanelProps) {
  if (risks.length === 0) {
    return (
      <p className="text-xs text-slate-400 text-center py-6">
        {message ?? 'No risks identified.'}
      </p>
    )
  }

  const sorted = [...risks].sort(
    (a, b) => (SEVERITY_ORDER[a.severity] ?? 3) - (SEVERITY_ORDER[b.severity] ?? 3),
  )
  const counts = sorted.reduce<Record<string, number>>((acc, r) => {
    acc[r.severity] = (acc[r.severity] ?? 0) + 1
    return acc
  }, {})

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        {(['HIGH', 'MEDIUM', 'LOW'] as const).map((sev) => (
          <span
            key={sev}
            className={cn('rounded-full border px-2.5 py-0.5 text-2xs font-semibold', SEVERITY_STYLES[sev])}
          >
            {counts[sev] ?? 0} {sev}
          </span>
        ))}
      </div>

      {sorted.map((risk, i) => (
        <div key={i} className="rounded-lg border border-slate-200 bg-white p-3 space-y-1.5">
          <div className="flex items-center gap-2">
            <AlertTriangle
              className={cn(
                'h-3.5 w-3.5 shrink-0',
                risk.severity === 'HIGH' ? 'text-red-500' : risk.severity === 'MEDIUM' ? 'text-amber-500' : 'text-slate-400',
              )}
            />
            <span
              className={cn(
                'rounded border px-1.5 py-px text-2xs font-semibold',
                SEVERITY_STYLES[risk.severity] ?? SEVERITY_STYLES.LOW,
              )}
            >
              {risk.severity}
            </span>
            <span className="text-2xs uppercase tracking-wide text-slate-400">{risk.category}</span>
          </div>
          <p className="text-sm text-slate-800">{risk.description}</p>
          {risk.recommendation && (
            <p className="text-xs text-slate-600">
              <span className="font-semibold">Recommendation:</span> {risk.recommendation}
            </p>
          )}
          {risk.source && <p className="text-2xs text-slate-400">{risk.source}</p>}
        </div>
      ))}
    </div>
  )
}
