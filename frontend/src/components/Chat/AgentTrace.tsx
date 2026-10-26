import { Check, Loader2, X } from 'lucide-react'
import { getAgentMeta } from '@/lib/agents'
import { cn } from '@/lib/utils'
import type { AgentTraceStep } from '@/lib/types'

function StatusIcon({ status }: { status: string }) {
  if (status === 'done') return <Check className="h-3.5 w-3.5 text-emerald-600" aria-label="done" />
  if (status === 'error') return <X className="h-3.5 w-3.5 text-red-600" aria-label="error" />
  return <Loader2 className="h-3.5 w-3.5 animate-spin text-brand" aria-label={status} />
}

interface AgentTraceProps {
  steps: AgentTraceStep[]
  isStreaming: boolean
}

/** Live view of what each agent is doing while an answer is being produced. */
export default function AgentTrace({ steps, isStreaming }: AgentTraceProps) {
  if (!isStreaming || steps.length === 0) return null

  return (
    <div className="ml-11 inline-flex flex-wrap items-center gap-x-4 gap-y-1.5 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs shadow-sm animate-in">
      {steps.map((step) => {
        const { label, Icon, color } = getAgentMeta(step.agent)
        return (
          <span key={step.agent} className="inline-flex items-center gap-1.5 text-slate-600">
            <Icon className={cn('h-3.5 w-3.5', color)} />
            {step.agent === 'orchestrator' && step.status === 'routing' ? 'Choosing agents' : label}
            <StatusIcon status={step.status} />
          </span>
        )
      })}
    </div>
  )
}
