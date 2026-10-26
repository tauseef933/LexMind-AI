import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import MessageBubble from './MessageBubble'
import type { ChatMessage, Source } from '@/lib/types'

vi.mock('@/lib/api', () => ({ downloadReportPdf: vi.fn() }))

function renderBubble(message: Partial<ChatMessage>) {
  const onCitationClick = vi.fn()
  render(
    <MessageBubble
      message={{ id: '1', role: 'assistant', content: '', ...message }}
      caseId="case-1"
      onCitationClick={onCitationClick}
    />,
  )
  return onCitationClick
}

describe('MessageBubble', () => {
  it('renders markdown headings, lists and bold text', () => {
    renderBubble({ content: '## Findings\n\n- **Term** is five years\n- Second point' })

    expect(screen.getByRole('heading', { name: 'Findings' })).toBeInTheDocument()
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    expect(screen.getByText('Term').tagName).toBe('STRONG')
  })

  it('turns inline citations into buttons that open the right page', () => {
    const onClick = renderBubble({
      content: 'Term is five years [Source: My NDA (v2).pdf, Page 3].',
    })

    fireEvent.click(screen.getByRole('button', { name: '[Source: My NDA (v2).pdf, Page 3]' }))
    expect(onClick).toHaveBeenCalledWith('My NDA (v2).pdf', 3)
  })

  it('also links citations written with \u3010\u3011 brackets (older saved answers)', () => {
    const onClick = renderBubble({ content: 'New York law \u3010Source: nda.pdf, Page 5\u3011.' })
    fireEvent.click(screen.getByRole('button', { name: '[Source: nda.pdf, Page 5]' }))
    expect(onClick).toHaveBeenCalledWith('nda.pdf', 5)
  })

  it('shows source pills for document chunks but not for research URLs', () => {
    const doc: Source = { text: 't', doc_id: 'd', filename: 'nda.pdf', page_number: 2, chunk_index: 0 }
    const onClick = renderBubble({
      content: 'Answer',
      sources: [doc, 'https://example.com/case-law' as unknown as Source],
    })

    const pill = screen.getByRole('button', { name: /nda\.pdf/ })
    fireEvent.click(pill)
    expect(onClick).toHaveBeenCalledWith('nda.pdf', 2)
    expect(screen.queryByText('https://example.com/case-law')).not.toBeInTheDocument()
  })

  it('shows one source pill per file and page', () => {
    const chunk = (i: number): Source => ({
      text: `t${i}`, doc_id: 'd', filename: 'nda.pdf', page_number: 5, chunk_index: i,
    })
    renderBubble({ content: 'Answer', sources: [chunk(0), chunk(1)] })
    expect(screen.getAllByRole('button', { name: /nda\.pdf/ })).toHaveLength(1)
  })

  it('opens normal links in a new tab', () => {
    renderBubble({ content: 'See [the statute](https://example.com/law).' })
    const link = screen.getByRole('link', { name: 'the statute' })
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('shows an action card for drafted actions', () => {
    renderBubble({
      content: 'Draft ready',
      actions: [{ action_type: 'email', to: 'a@b.com', subject: 'Hello there', body: 'Hi' }],
    })
    const link = screen.getByRole('link', { name: /open in mail app/i })
    expect(link.getAttribute('href')).toBe('mailto:a%40b.com?subject=Hello%20there&body=Hi')
  })

  it('copies the answer to the clipboard', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText } })
    renderBubble({ content: 'Term is five years [Source: nda.pdf, Page 3].' })

    fireEvent.click(screen.getByRole('button', { name: 'Copy answer' }))
    expect(writeText).toHaveBeenCalledWith('Term is five years [Source: nda.pdf, Page 3].')
    expect(await screen.findByRole('button', { name: 'Copied' })).toBeInTheDocument()
  })

  it('summarises which agents answered, flagging failures', () => {
    renderBubble({
      content: 'Answer',
      agentTrace: [
        { agent: 'orchestrator', status: 'done' },
        { agent: 'document_agent', status: 'done' },
        { agent: 'research_agent', status: 'error' },
      ],
    })
    expect(screen.getByText('Document Agent')).toBeInTheDocument()
    expect(screen.getByTitle('Research Agent failed')).toBeInTheDocument()
    expect(screen.queryByText('Orchestrator')).not.toBeInTheDocument()
  })

  it('has no footer while the answer is still streaming', () => {
    renderBubble({ content: 'Partial', isStreaming: true })
    expect(screen.queryByRole('button', { name: 'Copy answer' })).not.toBeInTheDocument()
  })

  it('shows typing dots while waiting for the first token', () => {
    const { container } = render(
      <MessageBubble
        message={{ id: '1', role: 'assistant', content: '', isStreaming: true }}
        caseId="c"
        onCitationClick={() => {}}
      />,
    )
    expect(container.querySelectorAll('.animate-bounce')).toHaveLength(3)
  })
})
