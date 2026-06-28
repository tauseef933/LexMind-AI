import { useCallback, useEffect, useRef, useState } from 'react'
import { getMessages } from '@/lib/api'
import { openChatStream } from '@/lib/api'
import type { AgentTraceStep, ChatMessage, Message, Source, SSEEvent } from '@/lib/types'

interface UseStreamingReturn {
  messages: ChatMessage[]
  agentTrace: AgentTraceStep[]
  isStreaming: boolean
  historyLoading: boolean
  sendMessage: (content: string, caseId: string, caseName: string) => Promise<void>
  clearMessages: () => void
}

function toChatMessage(row: Message): ChatMessage {
  return {
    id: row.id,
    role: row.role,
    content: row.content,
    sources: row.sources ?? undefined,
    agentTrace: row.agent_trace ?? undefined,
  }
}

export function useStreaming(caseId: string | null): UseStreamingReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [agentTrace, setAgentTrace] = useState<AgentTraceStep[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [historyLoading, setHistoryLoading] = useState(false)

  const assistantIdRef = useRef<string | null>(null)

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
      setMessages((prev) => [...prev, { id: userId, role: 'user', content }])

      const assistantId = crypto.randomUUID()
      assistantIdRef.current = assistantId
      setMessages((prev) => [
        ...prev,
        { id: assistantId, role: 'assistant', content: '', isStreaming: true },
      ])

      setAgentTrace([])
      setIsStreaming(true)

      try {
        const response = await openChatStream(content, activeCaseId, caseName)
        if (!response.body) throw new Error('No response body')

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        const collectedSources: Source[] = []
        const collectedTrace: AgentTraceStep[] = []

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
              collectedTrace.push(event.step)
              setAgentTrace([...collectedTrace])
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
            m.id === assistantIdRef.current
              ? { ...m, content: `Connection error: ${msg}`, isStreaming: false }
              : m,
          ),
        )
      } finally {
        setIsStreaming(false)
        assistantIdRef.current = null
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
