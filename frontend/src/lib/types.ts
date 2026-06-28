// ─── Core domain types ───────────────────────────────────────────────────────

export interface Case {
  id: string
  name: string
  client: string | null
  court: string | null
  hearing_date: string | null   // ISO date string "YYYY-MM-DD"
  status: 'active' | 'archived' | string
  created_at: string            // ISO datetime
  updated_at: string
}

export interface Document {
  id: string
  case_id: string | null
  filename: string
  file_type: string | null
  page_count: number | null
  ingested_at: string
}

export interface Message {
  id: string
  case_id: string | null
  role: 'user' | 'assistant'
  content: string
  agent_trace: AgentTraceStep[] | null   // parsed from JSON string
  sources: Source[] | null               // parsed from JSON string
  created_at: string
}

// ─── Agent / SSE streaming types ─────────────────────────────────────────────

export type AgentName =
  | 'orchestrator'
  | 'document_agent'
  | 'analytics_agent'
  | 'research_agent'
  | 'action_agent'

export interface AgentTraceStep {
  agent: AgentName | string
  status: 'routing' | 'done' | 'error' | string
}

export interface Source {
  text: string
  doc_id: string
  filename: string
  page_number: number
  chunk_index: number
}

// ─── SSE event payloads ───────────────────────────────────────────────────────

export interface SSEAgentTrace {
  type: 'agent_trace'
  step: AgentTraceStep
}

export interface SSEToken {
  type: 'token'
  content: string
}

export interface SSEDone {
  type: 'done'
  sources: Source[]
}

export interface SSEError {
  type: 'error'
  content: string
}

export type SSEEvent = SSEAgentTrace | SSEToken | SSEDone | SSEError

// ─── Chat state ───────────────────────────────────────────────────────────────

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
  agentTrace?: AgentTraceStep[]
  isStreaming?: boolean
}

// ─── Intelligence types ───────────────────────────────────────────────────────

export type RiskSeverity = 'HIGH' | 'MEDIUM' | 'LOW'
export type RiskCategory = 'evidence' | 'procedural' | 'legal' | 'witness' | 'timeline'

export interface Risk {
  severity: RiskSeverity
  category: RiskCategory
  description: string
  source: string
  recommendation: string
}

export interface RisksResponse {
  risks: Risk[]
  message?: string
  error?: string
}

export interface TimelineEvent {
  date: string
  event: string
  source: string
}

export interface TimelineResponse {
  timeline: TimelineEvent[]
}

export interface CaseSummary {
  parties: string[]
  charges_or_claims: string[]
  key_dates: Array<{ date: string; event: string }>
  evidence: string[]
  open_issues: string[]
  summary: string
  error?: string
}

export interface BillingRecord {
  id: string
  case_id: string | null
  invoice_number: string | null
  amount: number | null
  hours: number | null
  invoice_date: string | null
  dispute_flag: boolean | null
  dispute_reason: string | null
  status: string | null
}

export interface HearingPrepStrategy {
  key_arguments: string[]
  anticipated_objections: string[]
  witness_considerations: string[]
  document_priorities: string[]
  procedural_checklist: string[]
  opening_statement_outline: string
  error?: string
}

export interface HearingPrepResponse {
  hearing_date: string
  case_id: string
  summary: CaseSummary
  risks: Risk[]
  high_risk_count: number
  documents: Pick<Document, 'filename' | 'file_type' | 'page_count'>[]
  strategy: HearingPrepStrategy
}

// ─── API utility types ────────────────────────────────────────────────────────

export interface CreateCasePayload {
  name: string
  client?: string
  court?: string
  hearing_date?: string
  status?: string
}

export interface UploadResponse {
  doc_id: string
  status: string
}

export interface ChatRequest {
  content: string
  case_id: string
  case_name: string
}
