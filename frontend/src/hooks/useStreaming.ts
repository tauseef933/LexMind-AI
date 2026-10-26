import { useCallback, useEffect, useState } from 'react'
import { getMessages } from '@/lib/api'
import { openChatStream } from '@/lib/api'
import type {
  AgentTraceStep,
  ChatMessage,
  DraftAction,
  Message,
  Source,
  SSEEvent,
} from '@/lib/types'

interface UseStreamingReturn {
  messages: ChatMessage[]
  agentTrace: AgentTraceStep[]
  isStreaming: boolean
  historyLoading: boolean
  sendMessage: (content: string, caseId: string, caseName: string) => Promise<void>
  clearMessages: () => void
}

/** Replace the latest step of the same agent, or append a new one. */
function upsertStep(steps: AgentTraceStep[], step: AgentTraceStep): AgentTraceStep[] {
  const idx = steps.findIndex((s) => s.agent === step.agent)
  if (idx === -1) return [...steps, step]
  return steps.map((s, i) => (i === idx ? step : s))
}

function toChatMessage(row: Message): ChatMessage {
  const results = row.agent_trace ?? []
  const actions = results
    .filter((r) => r.agent === 'action_agent' && !r.error && r.action)
    .map((r) => ({ action_type: r.action_type, ...(r.action as object) }) as DraftAction)
  return {
    id: row.id,
    role: row.role,
    createdAt: row.created_at,
    content: row.content,
    sources: row.sources ?? undefined,
    agentTrace: results.map((r) => ({ agent: r.agent, status: r.error ? 'error' : 'done' })),
    actions: actions.length ? actions : undefined,
  }
}

export function useStreaming(caseId: string | null): UseStreamingReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [agentTrace, setAgentTrace] = useState<AgentTraceStep[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [historyLoading, setHistoryLoading] = useState(false)


  // Load persisted chat history whenever the active case changes
  useEffect(() => {
    if (!caseId) {
      setMessages([])
      setAgentTrace([])
      return
    }

    let cancelled = false
    setHistoryLoading(true)

    getMessages(caseId)
      .then((rows) => {
        if (!cancelled) setMessages(rows.map(toChatMessage))
      })
      .catch(() => {
        if (!cancelled) setMessages([])
      })
      .finally(() => {
        if (!cancelled) setHistoryLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [caseId])

  const sendMessage = useCallback(
    async (content: string, activeCaseId: string, caseName: string) => {
      if (isStreaming) return

      const userId = crypto.randomUUID()
      const now = new Date().toISOString()
      setMessages((prev) => [...prev, { id: userId, role: 'user', content, createdAt: now }])

      const assistantId = crypto.randomUUID()
      setMessages((prev) => [
        ...prev,
        { id: assistantId, role: 'assistant', content: '', isStreaming: true, createdAt: now },
      ])

      setAgentTrace([])
      setIsStreaming(true)

      try {
        const response = await openChatStream(content, activeCaseId, caseName)
        if (!response.ok) {
          // e.g. 429 rate limit, 401 bad API key, 404 unknown case
          const detail = await response
            .json()
            .then((body: { detail?: string }) => body.detail)
            .catch(() => undefined)
          throw new Error(detail ?? `Request failed (${response.status})`)
        }
        if (!response.body) throw new Error('No response body')

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        const collectedSources: Source[] = []
        let collectedTrace: AgentTraceStep[] = []

        while (true) {
          const { value, done } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() ?? ''

          for (const line of lines) {
            const trimmed = line.trim()
            if (!trimmed.startsWith('data:')) continue

            const jsonStr = trimmed.slice(5).trim()
            if (!jsonStr) continue

            let event: SSEEvent
            try {
              event = JSON.parse(jsonStr) as SSEEvent
            } catch {
              continue
            }

            if (event.type === 'agent_trace') {
              collectedTrace = upsertStep(collectedTrace, event.step)
              setAgentTrace(collectedTrace)
            } else if (event.type === 'token') {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, content: m.content + event.content }
                    : m,
                ),
              )
            } else if (event.type === 'done') {
              collectedSources.push(...event.sources)
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? {
                        ...m,
                        isStreaming: false,
                        sources: collectedSources,
                        agentTrace: collectedTrace,
                        actions: event.actions?.length ? event.actions : undefined,
                      }
                    : m,
                ),
              )
            } else if (event.type === 'error') {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? {
                        ...m,
                        content: `Error: ${event.content}`,
                        isStreaming: false,
                      }
                    : m,
                ),
              )
            }
          }
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err)
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, content: `Connection error: ${msg}`, isStreaming: false }
              : m,
          ),
        )
      } finally {
        setIsStreaming(false)
      }
    },
    [isStreaming],
  )

  const clearMessages = useCallback(() => {
    setMessages([])
    setAgentTrace([])
  }, [])

  return { messages, agentTrace, isStreaming, historyLoading, sendMessage, clearMessages }
}
