import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useStreaming } from './useStreaming'
import { getMessages, openChatStream } from '@/lib/api'
import type { Message } from '@/lib/types'

vi.mock('@/lib/api', () => ({
  getMessages: vi.fn(),
  openChatStream: vi.fn(),
}))

/** A fetch Response whose body yields the given raw chunks. */
function sseResponse(chunks: string[]): Response {
  const encoder = new TextEncoder()
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk))
      controller.close()
    },
  })
  return new Response(stream)
}

const sse = (payload: object) => `data: ${JSON.stringify(payload)}\n\n`

beforeEach(() => {
  vi.mocked(getMessages).mockResolvedValue([])
  vi.mocked(openChatStream).mockReset()
})

describe('useStreaming', () => {
  it('streams tokens, updates agent status in place and finishes with sources and actions', async () => {
    const done = sse({
      type: 'done',
      sources: [{ text: 't', doc_id: 'd', filename: 'nda.pdf', page_number: 2, chunk_index: 0 }],
      actions: [{ action_type: 'email', to: '', subject: 'S', body: 'B' }],
    })
    // Split one event across two network chunks to test buffering
    vi.mocked(openChatStream).mockResolvedValue(
      sseResponse([
        sse({ type: 'agent_trace', step: { agent: 'orchestrator', status: 'routing' } }),
        sse({ type: 'agent_trace', step: { agent: 'document_agent', status: 'running' } }),
        sse({ type: 'token', content: 'Hello ' }),
        sse({ type: 'token', content: 'world' }),
        sse({ type: 'agent_trace', step: { agent: 'orchestrator', status: 'done' } }),
        sse({ type: 'agent_trace', step: { agent: 'document_agent', status: 'done' } }),
        done.slice(0, 20),
        done.slice(20),
      ]),
    )

    const { result } = renderHook(() => useStreaming('case-1'))
    await waitFor(() => expect(result.current.historyLoading).toBe(false))
    await act(() => result.current.sendMessage('Hi?', 'case-1', 'Case'))

    const [user, assistant] = result.current.messages
    expect(user).toMatchObject({ role: 'user', content: 'Hi?' })
    expect(assistant).toMatchObject({ role: 'assistant', content: 'Hello world', isStreaming: false })
    expect(assistant.sources?.[0].page_number).toBe(2)
    expect(assistant.actions?.[0]).toMatchObject({ action_type: 'email', subject: 'S' })
    expect(result.current.agentTrace).toEqual([
      { agent: 'orchestrator', status: 'done' },
      { agent: 'document_agent', status: 'done' },
    ])
    expect(result.current.isStreaming).toBe(false)
  })

  it('shows the server error message', async () => {
    vi.mocked(openChatStream).mockResolvedValue(
      sseResponse([sse({ type: 'error', content: 'Something went wrong' })]),
    )
    const { result } = renderHook(() => useStreaming('case-1'))
    await waitFor(() => expect(result.current.historyLoading).toBe(false))
    await act(() => result.current.sendMessage('Hi?', 'case-1', 'Case'))

    expect(result.current.messages[1]).toMatchObject({
      content: 'Error: Something went wrong',
      isStreaming: false,
    })
  })

  it('reports connection failures', async () => {
    vi.mocked(openChatStream).mockRejectedValue(new Error('Failed to fetch'))
    const { result } = renderHook(() => useStreaming('case-1'))
    await waitFor(() => expect(result.current.historyLoading).toBe(false))
    await act(() => result.current.sendMessage('Hi?', 'case-1', 'Case'))

    expect(result.current.messages[1].content).toBe('Connection error: Failed to fetch')
  })

  it('shows the server message for HTTP errors such as rate limits', async () => {
    vi.mocked(openChatStream).mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Too many requests. Please wait and try again.' }), {
        status: 429,
      }),
    )
    const { result } = renderHook(() => useStreaming('case-1'))
    await waitFor(() => expect(result.current.historyLoading).toBe(false))
    await act(() => result.current.sendMessage('Hi?', 'case-1', 'Case'))

    expect(result.current.messages[1]).toMatchObject({
      content: 'Connection error: Too many requests. Please wait and try again.',
      isStreaming: false,
    })
  })

  it('rebuilds agent status and drafted actions from saved history', async () => {
    const row: Message = {
      id: 'm1',
      case_id: 'case-1',
      role: 'assistant',
      content: 'Saved answer',
      sources: null,
      created_at: '2026-10-26T10:00:00',
      agent_trace: [
        { agent: 'document_agent', answer: 'x' },
        { agent: 'research_agent', error: 'Legal research failed.' },
        {
          agent: 'action_agent',
          action_type: 'calendar',
          action: { title: 'Prep', start: '2026-11-03T10:00', end: null, location: '', attendees: [], description: '' },
        },
      ],
    }
    vi.mocked(getMessages).mockResolvedValue([row])

    const { result } = renderHook(() => useStreaming('case-1'))
    await waitFor(() => expect(result.current.messages).toHaveLength(1))

    const msg = result.current.messages[0]
    expect(msg.agentTrace).toEqual([
      { agent: 'document_agent', status: 'done' },
      { agent: 'research_agent', status: 'error' },
      { agent: 'action_agent', status: 'done' },
    ])
    expect(msg.actions).toEqual([
      { action_type: 'calendar', title: 'Prep', start: '2026-11-03T10:00', end: null, location: '', attendees: [], description: '' },
    ])
  })
})
