import { useState } from 'react'
import { Check, ChevronDown, ChevronRight, Bot, Search, BarChart2, Zap, BookOpen, Router } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { AgentTraceStep } from '@/lib/types'

const AGENT_META: Record<string, { label: string; Icon: React.ElementType; color: string }> = {
  orchestrator:    { label: 'Orchestrator',    Icon: Router,   color: 'text-violet-600' },
  document_agent:  { label: 'Document Agent',  Icon: BookOpen, color: 'text-blue-600'   },
  analytics_agent: { label: 'Analytics Agent', Icon: BarChart2,color: 'text-emerald-600'},
  research_agent:  { label: 'Research Agent',  Icon: Search,   color: 'text-amber-600'  },
  action_agent:    { label: 'Action Agent',    Icon: Zap,      color: 'text-rose-600'   },
}

function getAgentMeta(agent: string) {
  return AGENT_META[agent] ?? { label: agent, Icon: Bot, color: 'text-slate-500' }
}

function StatusBadge({ status }: { status: string }) {
  if (status === 'routing') {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-full px-2 py-0.5">
        <span className="h-1.5 w-1.5 rounded-full bg-amber-500 animate-pulse" />
        routing
      </span>
    )
  }
  if (status === 'error') {
    return (
      <span className="text-xs text-red-700 bg-red-50 border border-red-200 rounded-full px-2 py-0.5">
        error
      </span>
    )
  }
  if (status === 'done') {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-full px-2 py-0.5">
        <Check className="h-3 w-3" />
        done
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 text-xs text-blue-700 bg-blue-50 border border-blue-200 rounded-full px-2 py-0.5">
      <span className="h-1.5 w-1.5 rounded-full bg-blue-500 animate-pulse" />
      {status}
    </span>
  )
}

interface AgentTraceProps {
  steps: AgentTraceStep[]
  isStreaming: boolean
}

export default function AgentTrace({ steps, isStreaming }: AgentTraceProps) {
  const [expanded, setExpanded] = useState(true)

  if (steps.length === 0) return null

  const canCollapse = !isStreaming

  return (
    <div className="mx-5 mb-2 rounded-xl border border-slate-200 bg-slate-50/80 overflow-hidden text-sm">
      <button
        type="button"
        className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-slate-100/60 transition-colors"
        onClick={() => canCollapse && setExpanded((v) => !v)}
        disabled={!canCollapse}
      >
        <span className="font-medium text-slate-700 flex items-center gap-2">
          <Bot className="h-4 w-4 text-violet-600" />
          Agent activity
          {isStreaming && (
            <span className="inline-flex items-center gap-1 text-xs text-blue-600 font-normal">
              <span className="h-1.5 w-1.5 rounded-full bg-blue-500 animate-ping" />
              live
            </span>
          )}
        </span>
        {canCollapse && (
          expanded
            ? <ChevronDown className="h-4 w-4 text-slate-400" />
            : <ChevronRight className="h-4 w-4 text-slate-400" />
        )}
      </button>

      {expanded && (
        <ul className="px-4 pb-3 space-y-1.5">
          {steps.map((step, i) => {
            const { label, Icon, color } = getAgentMeta(step.agent)
            return (
              <li key={i} className="flex items-center gap-2">
                <Icon className={cn('h-3.5 w-3.5 shrink-0', color)} />
                <span className="flex-1 text-slate-600">{label}</span>
                <StatusBadge status={step.status} />
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
