import { BarChart2, BookOpen, Bot, Router, Search, Zap, type LucideIcon } from 'lucide-react'

export interface AgentMeta {
  label: string
  Icon: LucideIcon
  color: string
}

const AGENT_META: Record<string, AgentMeta> = {
  orchestrator: { label: 'Orchestrator', Icon: Router, color: 'text-violet-600' },
  document_agent: { label: 'Document Agent', Icon: BookOpen, color: 'text-blue-600' },
  analytics_agent: { label: 'Billing Agent', Icon: BarChart2, color: 'text-emerald-600' },
  research_agent: { label: 'Research Agent', Icon: Search, color: 'text-amber-600' },
  action_agent: { label: 'Action Agent', Icon: Zap, color: 'text-rose-600' },
}

export function getAgentMeta(agent: string): AgentMeta {
  return AGENT_META[agent] ?? { label: agent, Icon: Bot, color: 'text-slate-500' }
}
